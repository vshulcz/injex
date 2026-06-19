import asyncio
import inspect
import threading
from collections.abc import Callable
from contextlib import AsyncExitStack, ExitStack, asynccontextmanager, contextmanager
from typing import (
    Any,
    TypeVar,
    cast,
    overload,
)

from .errors import (
    AsyncResolutionRequiredException,
    ContainerValidationException,
    CyclicDependencyException,
    InvalidLifestyleException,
    MissingTypeAnnotationException,
    PropertyInjectionException,
    ServiceNotRegisteredException,
    ValidationError,
    _describe_service,
)
from .planning import (
    _cached_injected_properties,
    _cached_property_dependencies,
    _cached_type_hints,
    _DependencyPlan,
    _FactoryPlan,
    _get_callable_plan,
    _get_parameters,
    _get_type_hints,
    _make_constant_creator,
    _make_fast_raw_creator,
    _none_creator,
    _normalize_dependency_type,
    _ServicePlan,
)
from .registry import (
    _SCAN_ATTR,
    LifeStyle,
    OverrideContext,
    Registration,
    RegistrationType,
)

_MISSING = object()

T = TypeVar("T")


class _NotFlat(Exception):
    """Raised internally when a graph cannot be compiled to a flat creator."""


class Scope:
    __slots__ = ("_scoped_instances", "_stack", "container")

    def __init__(self, container: "Container"):
        self.container = container
        self._scoped_instances: dict[Any, Any] = {}
        # Holds sync resources opened in this scope; finalized (LIFO) on exit.
        self._stack = ExitStack()

    def __enter__(self) -> "Scope":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        # Finalize sync resources (LIFO), then drop per-scope instances.
        self._stack.close()
        self._scoped_instances.clear()

    @overload
    def resolve(self, interface: type[T], name: str | None = None) -> T: ...
    @overload
    def resolve(self, interface: str, name: str | None = None) -> Any: ...
    def resolve(self, interface: type | str, name: str | None = None) -> Any:
        """Resolve one service from this scope."""
        container = self.container
        if name is None:
            # A noscope creator only exists for graphs with no scoped services,
            # so it is safe to use inside a scope too (nothing is per-scope).
            try:
                creator = container._noscope_creators[interface]
            except KeyError:
                creator = container._prime_noscope_creator(interface)
            if creator is not None:
                return creator(None)
        return container._resolve_one(interface, self, name)

    @overload
    def resolve_all(self, interface: type[T], name: str | None = None) -> list[T]: ...
    @overload
    def resolve_all(self, interface: str, name: str | None = None) -> list[Any]: ...
    def resolve_all(self, interface: type | str, name: str | None = None) -> list[Any]:
        """Resolve all unnamed implementations registered for a type."""
        return self.container._resolve_in_scope(interface, self, name)


class AsyncScope:
    """Async resolution scope. Async resources opened inside it are finalized
    (LIFO) when the scope exits."""

    __slots__ = ("_scoped_instances", "_stack", "container")

    def __init__(self, container: "Container"):
        self.container = container
        self._scoped_instances: dict[Any, Any] = {}
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> "AsyncScope":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await self._stack.aclose()

    @overload
    async def aresolve(self, interface: type[T], name: str | None = None) -> T: ...
    @overload
    async def aresolve(self, interface: str, name: str | None = None) -> Any: ...
    async def aresolve(self, interface: type | str, name: str | None = None) -> Any:
        """Resolve one service from this async scope (awaits async factories)."""
        container = self.container
        if name is None:
            # A compiled noscope creator only exists for a graph with no
            # factories at all (see _build_fast_creator), so it can contain no
            # async work — resolve it directly and skip the coroutine walk.
            try:
                creator = container._noscope_creators[interface]
            except KeyError:
                creator = container._prime_noscope_creator(interface)
            if creator is not None:
                return creator(None)
        acreator = container._get_async_creator(interface, name)
        if acreator is not None:
            return await acreator[0](self)
        return await container._aresolve_one(interface, self, name, set())


class Container:
    __slots__ = (
        "_async_creators",
        "_async_inflight",
        "_async_resource_keys",
        "_async_stack",
        "_noscope_creators",
        "_registrations",
        "_resolving_local",
        "_singleton_lock",
        "_singletons",
        "_sync_resource_keys",
        "_sync_stack",
        "_version",
    )

    def __init__(self) -> None:
        self._registrations: dict[
            tuple[type | str, str | None], list[Registration]
        ] = {}
        self._singletons: dict[Any, Any] = {}
        # Guards first-time singleton construction so concurrent resolves build a
        # singleton once. Reentrant for nested singleton dependencies; only taken
        # on a cache miss, so the warm path stays lock-free.
        self._singleton_lock = threading.RLock()
        # Per-thread in-progress set for cycle detection on the interpreted sync
        # path. Thread-local so concurrent resolves (e.g. a threaded web server)
        # never see each other's in-progress types. The async path uses its own
        # per-call set; the compiled fast path needs no guard at all.
        self._resolving_local = threading.local()
        self._version = 0
        # Lazily created AsyncExitStack holding singleton async resources;
        # finalized by `await container.aclose()` at shutdown.
        self._async_stack: AsyncExitStack | None = None
        # instance_keys of singleton async resources entered on _async_stack, so
        # aclose() can evict them and avoid handing back a finalized object.
        self._async_resource_keys: set[Any] = set()
        # Direct interface -> creator dispatch for the common name=None,
        # no-scope-needed case. Skips the per-resolve key-tuple allocation and
        # registration attribute reads. Value is None when the interface is not
        # eligible for the no-scope fast path. Cleared on every invalidation.
        self._noscope_creators: dict[Any, Callable[[Any], Any] | None] = {}
        # Compiled async creators per (interface, name): an `async def` that
        # inlines the synchronous parts of the graph and awaits only genuine
        # async nodes, plus a flag for whether it needs an async scope.
        # Value is None when the graph can't be flattened (falls back to the
        # interpreted async walk). Cleared on every invalidation.
        self._async_creators: dict[
            Any,
            tuple[Callable[[Any], Any], bool] | None,
        ] = {}
        # In-flight singleton builds on the async path, keyed by instance_key, so
        # concurrent coroutines awaiting the same uncached singleton share one
        # build instead of each constructing their own.
        self._async_inflight: dict[Any, asyncio.Future[Any]] = {}
        # Lazily created ExitStack holding singleton sync resources; finalized by
        # container.close() at shutdown, with their instance_keys tracked so close()
        # can evict them (mirrors the async stack / aclose()).
        self._sync_stack: ExitStack | None = None
        self._sync_resource_keys: set[Any] = set()

    def __enter__(self) -> "Container":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    @property
    def _resolving(self) -> set[Any]:
        s = getattr(self._resolving_local, "value", None)
        if s is None:
            s = set()
            self._resolving_local.value = s
        return s

    def _invalidate_fast_creators(self) -> None:
        self._version += 1
        self._noscope_creators.clear()
        self._async_creators.clear()

    def register(
        self,
        interface: type,
        implementation: type | None = None,
        lifestyle: str = LifeStyle.TRANSIENT,
        name: str | None = None,
    ) -> None:
        """Register a class. ``implementation`` defaults to ``interface``.
        Dependencies are read from the constructor's type hints."""
        if lifestyle not in (
            LifeStyle.TRANSIENT,
            LifeStyle.SINGLETON,
            LifeStyle.SCOPED,
        ):
            raise InvalidLifestyleException(lifestyle)
        if implementation is None:
            implementation = interface
        key = (interface, name)
        registration = Registration(
            kind=RegistrationType.SERVICE,
            implementation=implementation,
            lifestyle=lifestyle,
        )
        self._registrations.setdefault(key, []).append(registration)
        self._invalidate_fast_creators()

    def register_factory(
        self,
        interface: type,
        factory: Callable[..., Any],
        lifestyle: str = LifeStyle.TRANSIENT,
        name: str | None = None,
    ) -> None:
        """Register a callable that builds the service. The factory's own
        parameters are injected. Coroutine factories and async generators
        (``async def ... yield``) are supported via aresolve()/ascope()."""
        if not callable(factory):
            raise ValueError("Factory must be callable")
        if lifestyle not in (
            LifeStyle.TRANSIENT,
            LifeStyle.SINGLETON,
            LifeStyle.SCOPED,
        ):
            raise InvalidLifestyleException(lifestyle)
        key = (interface, name)
        registration = Registration(
            kind=RegistrationType.FACTORY, factory=factory, lifestyle=lifestyle
        )
        registration.is_resource = inspect.isasyncgenfunction(factory)
        registration.is_sync_resource = inspect.isgeneratorfunction(factory)
        registration.is_async = inspect.iscoroutinefunction(factory)
        self._registrations.setdefault(key, []).append(registration)
        self._invalidate_fast_creators()

    def add_instance(
        self, interface: type, instance: Any, name: str | None = None
    ) -> None:
        """Register an already-built object. Resolves return it as-is."""
        key = (interface, name)
        registration = Registration(
            kind=RegistrationType.INSTANCE,
            instance=instance,
            lifestyle=LifeStyle.SINGLETON,
        )
        self._registrations.setdefault(key, []).append(registration)
        self._invalidate_fast_creators()

    def override(
        self,
        interface: type,
        implementation: type | None = None,
        *,
        factory: Callable[..., Any] | None = None,
        instance: Any | None = None,
        lifestyle: str = LifeStyle.TRANSIENT,
        name: str | None = None,
    ) -> OverrideContext:
        """Temporarily replace a registration; returns a context manager that
        restores the previous one on exit. Handy for tests."""
        provided = sum(
            value is not None for value in (implementation, factory, instance)
        )
        if provided > 1:
            raise ValueError(
                "Provide only one override target: "
                "implementation, factory, or instance."
            )
        if lifestyle not in (
            LifeStyle.TRANSIENT,
            LifeStyle.SINGLETON,
            LifeStyle.SCOPED,
        ):
            raise InvalidLifestyleException(lifestyle)

        if instance is not None:
            registration = Registration(
                kind=RegistrationType.INSTANCE,
                instance=instance,
                lifestyle=LifeStyle.SINGLETON,
            )
        elif factory is not None:
            if not callable(factory):
                raise ValueError("Factory must be callable")
            registration = Registration(
                kind=RegistrationType.FACTORY,
                factory=factory,
                lifestyle=lifestyle,
            )
            registration.is_resource = inspect.isasyncgenfunction(factory)
            registration.is_sync_resource = inspect.isgeneratorfunction(factory)
            registration.is_async = inspect.iscoroutinefunction(factory)
        else:
            if implementation is None:
                implementation = interface
            registration = Registration(
                kind=RegistrationType.SERVICE,
                implementation=implementation,
                lifestyle=lifestyle,
            )

        return OverrideContext(self, (interface, name), registration)

    def _pop_singletons_for_key(
        self, key: tuple[type | str, str | None]
    ) -> dict[Any, Any]:
        removed = {}
        for instance_key in list(self._singletons):
            if instance_key[0] == key:
                removed[instance_key] = self._singletons.pop(instance_key)
        return removed

    @overload
    def resolve(self, interface: type[T], name: str | None = None) -> T: ...
    @overload
    def resolve(self, interface: str, name: str | None = None) -> Any: ...
    def resolve(self, interface: type | str, name: str | None = None) -> Any:
        """Resolve one service. Raises AsyncResolutionRequiredException if the
        graph needs async work — use aresolve()/ascope() then."""
        if name is None:
            try:
                creator = self._noscope_creators[interface]
            except KeyError:
                creator = self._prime_noscope_creator(interface)
            if creator is not None:
                return creator(None)
            self._guard_top_sync_resource(interface, None)
            scope = Scope(self)
            return self._resolve_one(interface, scope, None)
        return self._resolve_slow(interface, name)

    def _guard_top_sync_resource(self, interface: type | str, name: str | None) -> None:
        registrations = self._registrations.get((interface, name))
        if registrations:
            registration = registrations[0]
            if registration.is_sync_resource and registration.lifestyle in (
                LifeStyle.TRANSIENT,
                LifeStyle.SCOPED,
            ):
                raise ValueError(
                    f"{_describe_service(interface)} is a {registration.lifestyle} "
                    "resource; resolve() would finalize it immediately. Resolve it "
                    "inside 'with container.create_scope() as scope: "
                    "scope.resolve(...)'."
                )

    def _prime_noscope_creator(
        self, interface: type | str
    ) -> Callable[[Any], Any] | None:
        creator: Callable[[Any], Any] | None = None
        registrations = self._registrations.get((interface, None))
        if registrations:
            registration = registrations[0]
            self._get_fast_creator(registration, (interface, None))
            if (
                registration.fast_creator is not None
                and not registration.fast_creator_needs_scope
            ):
                creator = registration.fast_creator
                # A scope-free singleton root is immutable until invalidation
                # (which rebuilds this entry). Realize it once and dispatch a
                # plain constant, skipping the cached-getter's sentinel check.
                if registration.lifestyle == LifeStyle.SINGLETON:
                    creator = _make_constant_creator(creator(None))
        self._noscope_creators[interface] = creator
        return creator

    def _resolve_slow(self, interface: type | str, name: str | None) -> Any:
        key = (interface, name)
        registrations = self._registrations.get(key)
        if registrations:
            registration = registrations[0]
            if registration.fast_creator_version != self._version:
                self._get_fast_creator(registration, key)
            fast_creator = registration.fast_creator
            if fast_creator is not None and not registration.fast_creator_needs_scope:
                return fast_creator(None)
        self._guard_top_sync_resource(interface, name)
        scope = self.create_scope()
        return self._resolve_one(interface, scope, name)

    @overload
    def resolve_all(self, interface: type[T], name: str | None = None) -> list[T]: ...
    @overload
    def resolve_all(self, interface: str, name: str | None = None) -> list[Any]: ...
    def resolve_all(self, interface: type | str, name: str | None = None) -> list[Any]:
        """Resolve all unnamed implementations registered for a type."""
        scope = self.create_scope()
        return scope.resolve_all(interface, name)

    def create_scope(self) -> Scope:
        """Open a sync scope. Scoped services are cached per-scope; for async
        resources use ``async with container.ascope()`` instead."""
        return Scope(self)

    def scan(self, *sources: Any) -> None:
        """Register every ``@injectable`` class found in the given modules.

        Pass modules (only classes *defined* there are registered, not imported
        ones) or any iterable of classes. Registration is explicit — it happens
        here, not as an import side effect.
        """
        for source in sources:
            if inspect.ismodule(source):
                candidates = [
                    obj
                    for obj in vars(source).values()
                    if isinstance(obj, type)
                    and getattr(obj, "__module__", None) == source.__name__
                ]
            else:
                candidates = list(source)
            for obj in candidates:
                info = obj.__dict__.get(_SCAN_ATTR)
                if info is None:
                    continue
                interface = info["provides"] or obj
                self.register(
                    interface,
                    obj,
                    lifestyle=info["lifestyle"],
                    name=info["name"],
                )

    def call(self, func: Callable[..., T], /, **overrides: Any) -> T:
        """Call ``func``, injecting its annotated parameters from the container.

        Parameters passed in ``overrides`` are used as-is instead of being
        resolved, so a handler can receive both container services and
        per-call values (a request, parsed args, a message)::

            container.call(handle_request, request=req)
        """
        plan = _get_callable_plan(func)
        scope = self.create_scope()
        kwargs: dict[str, Any] = dict(overrides)
        for dependency_plan in plan.dependencies:
            if dependency_plan.name in overrides:
                continue
            if dependency_plan.inject_container:
                kwargs[dependency_plan.name] = self
            else:
                kwargs[dependency_plan.name] = self._resolve_dependency_plan(
                    dependency_plan, scope, func
                )
        return func(**kwargs)

    def validate(self) -> list[ValidationError]:
        """Validate registered dependency graphs without creating service instances."""
        errors: list[ValidationError] = []
        seen: set[str] = set()
        for key, registrations in self._registrations.items():
            for registration in registrations:
                for error in self._validate_registration(key, registration, []):
                    # A shared dependency is reached from several roots; report
                    # each distinct problem once.
                    marker = str(error)
                    if marker not in seen:
                        seen.add(marker)
                        errors.append(error)
        return errors

    def assert_valid(self) -> None:
        """Raise ContainerValidationException when any registration is invalid."""
        errors = self.validate()
        if errors:
            raise ContainerValidationException(errors)

    def _resolve_in_scope(
        self, interface: type | str, scope: Scope, name: str | None = None
    ) -> list[Any]:
        key = (interface, name)
        registrations = self._registrations.get(key, [])
        instances = []
        for registration in registrations:
            instance = self._get_instance_from_registration(registration, scope, key)
            instances.append(instance)
        return instances

    def _resolve_one(
        self, interface: type | str, scope: Scope, name: str | None = None
    ) -> Any:
        key = (interface, name)
        registrations = self._registrations.get(key)
        if not registrations:
            interface_name = _describe_service(interface)
            if name is not None:
                interface_name += f" with name '{name}'"
            raise ServiceNotRegisteredException(interface_name)
        return self._get_instance_from_registration(registrations[0], scope, key)

    def _validate_registration(
        self,
        key: tuple[type | str, str | None],
        registration: Registration,
        path: list[tuple[type | str, str | None]],
    ) -> list[ValidationError]:
        if registration.kind == RegistrationType.INSTANCE:
            return []

        if key in path:
            cycle = [*path, key]
            return [
                ValidationError(
                    key[0],
                    key[1],
                    "Cyclic dependency detected: "
                    + " -> ".join(_describe_service(item[0]) for item in cycle)
                    + ".",
                )
            ]

        if registration.kind == RegistrationType.SERVICE:
            if registration.implementation is None:
                return [
                    ValidationError(
                        key[0], key[1], "Service registration has no implementation."
                    )
                ]
            return self._validate_class(registration.implementation, key, [*path, key])

        if registration.kind == RegistrationType.FACTORY:
            if registration.factory is None:
                return [
                    ValidationError(key[0], key[1], "Factory registration is empty.")
                ]
            return self._validate_callable(registration.factory, key, [*path, key])

        return [ValidationError(key[0], key[1], "Registration kind is not supported.")]

    def _validate_class(
        self,
        cls: type,
        source_key: tuple[type | str, str | None],
        path: list[tuple[type | str, str | None]],
    ) -> list[ValidationError]:
        errors: list[ValidationError] = []
        constructor = cls.__init__  # type: ignore[misc]
        if constructor is not object.__init__:
            errors.extend(
                self._validate_callable(constructor, source_key, path, skip_self=True)
            )

        for name, attr in _cached_injected_properties(cast(Any, cls)):
            try:
                type_hints = _cached_type_hints(attr)
            except Exception as exc:
                errors.append(
                    ValidationError(
                        source_key[0],
                        source_key[1],
                        f"Cannot read type hints for injected property '{name}': {exc}",
                    )
                )
                continue
            dependency_type = type_hints.get("return")
            if dependency_type is None:
                errors.append(
                    ValidationError(
                        source_key[0],
                        source_key[1],
                        f"Injected property '{name}' has no return type annotation.",
                    )
                )
                continue
            errors.extend(
                self._validate_dependency(dependency_type, source_key, path, name)
            )
        return errors

    def _validate_callable(
        self,
        func: Callable[..., Any],
        source_key: tuple[type | str, str | None],
        path: list[tuple[type | str, str | None]],
        skip_self: bool = False,
    ) -> list[ValidationError]:
        errors: list[ValidationError] = []
        try:
            parameters = _get_parameters(func)
        except Exception as exc:
            return [
                ValidationError(
                    source_key[0], source_key[1], f"Cannot inspect dependencies: {exc}"
                )
            ]
        try:
            type_hints = _get_type_hints(func)
        except Exception:
            type_hints = {}

        for name, param in parameters:
            if skip_self and name == "self":
                continue
            if param.annotation == inspect.Parameter.empty and name not in type_hints:
                if name == "container":
                    continue
                errors.append(
                    ValidationError(
                        source_key[0],
                        source_key[1],
                        f"Missing type annotation for dependency '{name}'.",
                    )
                )
                continue
            dependency_type = type_hints.get(name, param.annotation)
            if isinstance(param.annotation, str):
                raw_dependency_key = self._get_validation_key(param.annotation)
                if raw_dependency_key in self._registrations:
                    dependency_type = param.annotation
            errors.extend(
                self._validate_dependency(
                    dependency_type,
                    source_key,
                    path,
                    name,
                    has_default=param.default != inspect.Parameter.empty,
                )
            )
        return errors

    def _validate_dependency(
        self,
        dependency_type: Any,
        source_key: tuple[type | str, str | None],
        path: list[tuple[type | str, str | None]],
        dependency_name: str,
        has_default: bool = False,
    ) -> list[ValidationError]:
        dependency_type, is_optional, dep_name = _normalize_dependency_type(
            dependency_type
        )

        base_key = self._get_validation_key(dependency_type)
        dependency_key = (base_key[0], dep_name)
        registrations = self._registrations.get(dependency_key, [])
        if not registrations:
            if is_optional or has_default:
                return []
            return [
                ValidationError(
                    source_key[0],
                    source_key[1],
                    f"Dependency '{dependency_name}' is not registered: "
                    f"{_describe_service(dependency_type)}.",
                )
            ]

        errors: list[ValidationError] = []
        for registration in registrations:
            errors.extend(
                self._validate_registration(dependency_key, registration, path)
            )
        return errors

    def _get_validation_key(self, dependency_type: Any) -> tuple[type | str, None]:
        if isinstance(dependency_type, str):
            for registered_service, registered_name in self._registrations:
                if registered_name is None and (
                    registered_service == dependency_type
                    or getattr(registered_service, "__name__", None) == dependency_type
                ):
                    return (registered_service, None)
        return (dependency_type, None)

    def _get_fast_creator(
        self,
        registration: Registration,
        key: tuple[type | str, str | None],
    ) -> Callable[[Scope], Any] | None:
        if registration.fast_creator_version == self._version:
            return registration.fast_creator

        fast_creator = self._build_flat_creator(registration, key)
        if fast_creator is None:
            fast_creator = self._build_fast_creator(registration, key, set())
        if fast_creator is None:
            registration.fast_creator = None
            registration.fast_creator_needs_scope = False
        else:
            registration.fast_creator, registration.fast_creator_needs_scope = (
                fast_creator
            )
        registration.fast_creator_version = self._version
        return registration.fast_creator

    def _build_flat_creator(
        self,
        registration: Registration,
        key: tuple[type | str, str | None],
    ) -> tuple[Callable[[Any], Any], bool] | None:
        """Compile a flat creator for a transient service graph.

        Transient services are inlined into a single constructed expression;
        shared singletons/instances are computed once (common-subexpression
        elimination) and reused. This removes the per-resolve closure call for
        every intermediate transient and the duplicate work for singletons used
        more than once.

        Singleton, scoped, and instance leaves reuse the existing nested-closure
        creators (so caching, laziness, and invalidation are unchanged); only the
        transient construction spine is flattened. Returns ``None`` for any graph
        shape it cannot handle, so the caller falls back to the nested-closure
        builder and then to the interpreted path. No service names, class names,
        or user values are ever interpolated into generated source — only opaque
        generated symbols bound in a private namespace.
        """
        if (
            registration.kind != RegistrationType.SERVICE
            or registration.lifestyle != LifeStyle.TRANSIENT
        ):
            return None

        namespace: dict[str, Any] = {}
        prelude: list[str] = []
        shared: dict[Any, str] = {}
        counter = [0]
        needs_scope = [False]

        def bind(obj: Any, prefix: str) -> str:
            counter[0] += 1
            sym = f"{prefix}{counter[0]}"
            namespace[sym] = obj
            return sym

        def emit(
            reg: Registration,
            node_key: tuple[type | str, str | None],
            path: frozenset[Any],
        ) -> str:
            if reg.kind == RegistrationType.INSTANCE:
                if node_key in shared:
                    return shared[node_key]
                sym = bind(reg.instance, "c")
                shared[node_key] = sym
                return sym

            if reg.kind != RegistrationType.SERVICE:
                raise _NotFlat

            cls = reg.implementation
            if cls is None or node_key in path:
                raise _NotFlat

            plan = self._get_service_plan(reg)
            if plan.property_dependencies:
                raise _NotFlat

            lifestyle = reg.lifestyle
            if lifestyle in (LifeStyle.SINGLETON, LifeStyle.SCOPED):
                if node_key in shared:
                    return shared[node_key]
                built = self._build_fast_creator(reg, node_key, set())
                if built is None:
                    raise _NotFlat
                leaf_creator, leaf_needs_scope = built
                # A singleton whose subgraph needs no scope is immutable until the
                # next invalidation (which rebuilds this creator). Realize it once
                # here and inline the instance as a constant, so the generated code
                # constructs the transient spine with zero getter calls.
                if lifestyle == LifeStyle.SINGLETON and not leaf_needs_scope:
                    sym = bind(leaf_creator(None), "s")  # type: ignore[arg-type]
                    shared[node_key] = sym
                    return sym
                if lifestyle == LifeStyle.SCOPED or leaf_needs_scope:
                    needs_scope[0] = True
                getter = bind(leaf_creator, "g")
                counter[0] += 1
                var = f"v{counter[0]}"
                prelude.append(f"{var} = {getter}(scope)")
                shared[node_key] = var
                return var

            # Transient: inline the constructor, recursing into dependencies.
            child_path = path | {node_key}
            child_exprs: list[str] = []
            for dependency_plan in plan.dependencies:
                if dependency_plan.inject_container:
                    raise _NotFlat
                if dependency_plan.dependency_type == inspect.Parameter.empty:
                    raise _NotFlat
                dependency_key = dependency_plan.dependency_key
                if dependency_key is None:
                    raise _NotFlat
                dependency_regs = self._registrations.get(dependency_key)
                if not dependency_regs:
                    if dependency_plan.has_default:
                        child_exprs.append(bind(dependency_plan.default, "d"))
                        continue
                    if dependency_plan.is_optional:
                        child_exprs.append("None")
                        continue
                    raise _NotFlat
                child_exprs.append(emit(dependency_regs[0], dependency_key, child_path))

            cls_sym = bind(cls, "t")
            return f"{cls_sym}({', '.join(child_exprs)})"

        try:
            root_expr = emit(registration, key, frozenset())
        except _NotFlat:
            return None

        source_lines = ["def _flat(scope):"]
        source_lines.extend(f"    {line}" for line in prelude)
        source_lines.append(f"    return {root_expr}")
        local: dict[str, Any] = {}
        exec("\n".join(source_lines), namespace, local)
        return local["_flat"], needs_scope[0]

    def _get_async_creator(
        self, interface: type | str, name: str | None
    ) -> tuple[Callable[[Any], Any], bool] | None:
        # Cache under the bare interface for the common name=None case so the
        # hot path does a direct dict lookup with no per-call tuple allocation.
        cache_key: Any = interface if name is None else (interface, name)
        cached = self._async_creators.get(cache_key, _MISSING)
        if cached is not _MISSING:
            return cached  # type: ignore[return-value]
        reg_key = (interface, name)
        registrations = self._registrations.get(reg_key)
        result: tuple[Callable[[Any], Any], bool] | None = None
        if registrations:
            result = self._build_async_flat_creator(registrations[0], reg_key)
        self._async_creators[cache_key] = result
        return result

    def _build_async_flat_creator(
        self,
        registration: Registration,
        key: tuple[type | str, str | None],
    ) -> tuple[Callable[[Any], Any], bool] | None:
        """Compile an ``async def`` creator that inlines the synchronous parts of
        the graph and awaits only genuine async nodes.

        Synchronous subgraphs reuse the compiled sync fast creator (no coroutine
        per node); async factories and async resources are delegated to the
        interpreted async path through a bound getter and awaited once. Returns
        ``None`` for any shape it cannot flatten (cycles touching inlined nodes,
        property injection on an inlined transient, container injection), so the
        caller falls back to the fully interpreted async walk. As in the sync
        builder, no user names or values are interpolated into generated source.
        """
        namespace: dict[str, Any] = {}
        prelude: list[str] = []
        shared: dict[Any, str] = {}
        counter = [0]
        needs_scope = [False]

        def bind(obj: Any, prefix: str) -> str:
            counter[0] += 1
            sym = f"{prefix}{counter[0]}"
            namespace[sym] = obj
            return sym

        def delegate(reg: Registration, node_key: tuple[type | str, str | None]) -> str:
            lifestyle = reg.lifestyle
            if lifestyle == LifeStyle.SCOPED or (
                reg.is_resource and lifestyle == LifeStyle.TRANSIENT
            ):
                needs_scope[0] = True

            def getter(
                scope: Any, _reg: Registration = reg, _key: Any = node_key
            ) -> Any:
                return self._aget_instance_from_registration(_reg, scope, _key, set())

            sym = bind(getter, "ag")
            if lifestyle == LifeStyle.TRANSIENT:
                return f"(await {sym}(scope))"
            if node_key in shared:
                return shared[node_key]
            counter[0] += 1
            var = f"v{counter[0]}"
            # Cached singleton/scoped: check the cache synchronously and only
            # create+await the getter coroutine on a miss. After warmup this is a
            # plain dict lookup with no coroutine churn.
            ms = bind(_MISSING, "m")
            if lifestyle == LifeStyle.SINGLETON:
                ik = bind((node_key, reg), "ik")
                sg = bind(self._singletons.get, "sg")
                prelude.append(f"{var} = {sg}({ik}, {ms})")
                prelude.append(f"if {var} is {ms}:")
                prelude.append(f"    {var} = await {sym}(scope)")
            elif lifestyle == LifeStyle.SCOPED:
                ik = bind((node_key, reg), "ik")
                prelude.append(f"{var} = scope._scoped_instances.get({ik}, {ms})")
                prelude.append(f"if {var} is {ms}:")
                prelude.append(f"    {var} = await {sym}(scope)")
            else:
                prelude.append(f"{var} = await {sym}(scope)")
            shared[node_key] = var
            return var

        def emit(
            reg: Registration,
            node_key: tuple[type | str, str | None],
            path: frozenset[Any],
        ) -> str:
            if reg.kind == RegistrationType.INSTANCE:
                if node_key in shared:
                    return shared[node_key]
                sym = bind(reg.instance, "c")
                shared[node_key] = sym
                return sym

            built = self._build_fast_creator(reg, node_key, set())
            if built is not None:
                creator, leaf_needs_scope = built
                # Realize a scope-free singleton once and inline it as a constant
                # (same reasoning as the sync flat builder).
                if reg.lifestyle == LifeStyle.SINGLETON and not leaf_needs_scope:
                    if node_key in shared:
                        return shared[node_key]
                    sym = bind(creator(None), "s")  # type: ignore[arg-type]
                    shared[node_key] = sym
                    return sym
                if leaf_needs_scope:
                    needs_scope[0] = True
                gsym = bind(creator, "g")
                if reg.lifestyle == LifeStyle.TRANSIENT:
                    return f"{gsym}(scope)"
                if node_key in shared:
                    return shared[node_key]
                counter[0] += 1
                var = f"v{counter[0]}"
                prelude.append(f"{var} = {gsym}(scope)")
                shared[node_key] = var
                return var

            # Async node. Inline a plain transient constructor; delegate factories,
            # async resources, and cached (singleton/scoped) async services.
            if reg.kind == RegistrationType.SERVICE and (
                reg.lifestyle == LifeStyle.TRANSIENT
            ):
                cls = reg.implementation
                if cls is None or node_key in path:
                    raise _NotFlat
                plan = self._get_service_plan(reg)
                if plan.property_dependencies:
                    return delegate(reg, node_key)
                child_path = path | {node_key}
                child_exprs: list[str] = []
                for dependency_plan in plan.dependencies:
                    if dependency_plan.inject_container:
                        raise _NotFlat
                    if dependency_plan.dependency_type == inspect.Parameter.empty:
                        raise _NotFlat
                    dependency_key = dependency_plan.dependency_key
                    if dependency_key is None:
                        raise _NotFlat
                    dependency_regs = self._registrations.get(dependency_key)
                    if not dependency_regs:
                        if dependency_plan.has_default:
                            child_exprs.append(bind(dependency_plan.default, "d"))
                            continue
                        if dependency_plan.is_optional:
                            child_exprs.append("None")
                            continue
                        raise _NotFlat
                    child_exprs.append(
                        emit(dependency_regs[0], dependency_key, child_path)
                    )
                cls_sym = bind(cls, "t")
                return f"{cls_sym}({', '.join(child_exprs)})"

            return delegate(reg, node_key)

        try:
            root_expr = emit(registration, key, frozenset())
        except _NotFlat:
            return None

        source_lines = ["async def _aflat(scope):"]
        source_lines.extend(f"    {line}" for line in prelude)
        source_lines.append(f"    return {root_expr}")
        local: dict[str, Any] = {}
        exec("\n".join(source_lines), namespace, local)
        return local["_aflat"], needs_scope[0]

    def _build_fast_creator(
        self,
        registration: Registration,
        key: tuple[type | str, str | None],
        path: set[tuple[type | str, str | None]],
    ) -> tuple[Callable[[Scope], Any], bool] | None:
        if registration.kind == RegistrationType.INSTANCE:
            instance = registration.instance
            return lambda scope: instance, False

        if registration.kind != RegistrationType.SERVICE:
            return None

        cls = registration.implementation
        if cls is None or key in path:
            return None

        plan = self._get_service_plan(registration)
        if plan.property_dependencies:
            return None

        path.add(key)
        dependency_creators: list[Callable[[Scope], Any]] = []
        needs_scope = registration.lifestyle == LifeStyle.SCOPED
        try:
            for dependency_plan in plan.dependencies:
                if dependency_plan.inject_container:
                    return None
                if dependency_plan.dependency_type == inspect.Parameter.empty:
                    return None

                dependency_key = dependency_plan.dependency_key
                if dependency_key is None:
                    return None

                registrations = self._registrations.get(dependency_key)
                if not registrations:
                    if dependency_plan.has_default:
                        dependency_creators.append(
                            _make_constant_creator(dependency_plan.default)
                        )
                        continue
                    if dependency_plan.is_optional:
                        dependency_creators.append(_none_creator)
                        continue
                    return None

                dependency_creator = self._build_fast_creator(
                    registrations[0], dependency_key, path
                )
                if dependency_creator is None:
                    return None
                creator, dependency_needs_scope = dependency_creator
                needs_scope = needs_scope or dependency_needs_scope
                dependency_creators.append(creator)
        finally:
            path.remove(key)

        # A fast creator is only built when the whole subgraph below `cls` is
        # statically known to be acyclic and fully registered (cycles make
        # `_build_fast_creator` return None via the `key in path` guard above).
        # The runtime cycle guard can therefore never fire on this path, so we
        # use the unguarded raw creator and skip the per-resolve set churn.
        create_raw = _make_fast_raw_creator(cls, dependency_creators)

        if registration.lifestyle == LifeStyle.TRANSIENT:
            return create_raw, needs_scope

        instance_key = (key, registration)
        if registration.lifestyle == LifeStyle.SINGLETON:
            sentinel = object()
            cached_instance = [sentinel]
            singletons = self._singletons
            lock = self._singleton_lock

            def create_singleton(scope: Scope) -> Any:
                instance = cached_instance[0]
                if instance is not sentinel:
                    return instance
                with lock:
                    instance = cached_instance[0]
                    if instance is not sentinel:
                        return instance
                    if instance_key in singletons:
                        instance = singletons[instance_key]
                        cached_instance[0] = instance
                        return instance
                    instance = create_raw(scope)
                    singletons[instance_key] = instance
                    cached_instance[0] = instance
                    return instance

            return create_singleton, needs_scope

        if registration.lifestyle == LifeStyle.SCOPED:

            def create_scoped(scope: Scope) -> Any:
                if instance_key in scope._scoped_instances:
                    return scope._scoped_instances[instance_key]
                instance = create_raw(scope)
                scope._scoped_instances[instance_key] = instance
                return instance

            return create_scoped, True

        return None

    def _get_or_create_singleton(
        self,
        instance_key: Any,
        registration: Registration,
        scope: Scope,
    ) -> Any:
        # Double-checked under the lock: a concurrent first resolve must build
        # the singleton once and every caller must get that one instance.
        with self._singleton_lock:
            existing = self._singletons.get(instance_key, _MISSING)
            if existing is not _MISSING:
                return existing
            instance = self._create_instance_from_registration(registration, scope)
            self._singletons[instance_key] = instance
            if registration.is_sync_resource:
                self._sync_resource_keys.add(instance_key)
            return instance

    def _get_instance_from_registration(
        self,
        registration: Registration,
        scope: Scope,
        key: tuple[type | str, str | None],
    ) -> Any:
        fast_creator = self._get_fast_creator(registration, key)
        if fast_creator is not None:
            return fast_creator(scope)

        instance_key = (key, registration)
        if registration.kind == RegistrationType.INSTANCE:
            return registration.instance

        lifestyle = registration.lifestyle

        if lifestyle == LifeStyle.SINGLETON:
            existing = self._singletons.get(instance_key, _MISSING)
            if existing is not _MISSING:
                return existing
            return self._get_or_create_singleton(instance_key, registration, scope)
        elif lifestyle == LifeStyle.SCOPED:
            if instance_key in scope._scoped_instances:
                return scope._scoped_instances[instance_key]
            instance = self._create_instance_from_registration(registration, scope)
            scope._scoped_instances[instance_key] = instance
            return instance
        else:  # transient
            return self._create_instance_from_registration(registration, scope)

    def _create_instance_from_registration(
        self, registration: Registration, scope: Scope
    ) -> Any:
        if registration.kind == RegistrationType.SERVICE:
            if registration.implementation is not None:
                return self._create_service_from_registration(registration, scope)
            else:
                raise ValueError(
                    "Implementation cannot be None for service registration."
                )
        elif registration.kind == RegistrationType.FACTORY:
            if registration.factory is not None:
                return self._invoke_factory_registration(registration, scope)
            else:
                raise ValueError("Factory cannot be None for factory registration.")
        else:
            raise ValueError(f"Invalid registration kind: {registration.kind}")

    def _get_service_plan(self, registration: Registration) -> _ServicePlan:
        if registration.plan is not None:
            return registration.plan  # type: ignore[return-value]

        cls = registration.implementation
        if cls is None:
            raise ValueError("Implementation cannot be None for service registration.")

        constructor = cls.__init__  # type: ignore[misc]
        dependencies: tuple[_DependencyPlan, ...] = ()
        if constructor is not object.__init__:
            dependencies = _get_callable_plan(constructor, skip_self=True).dependencies
        plan = _ServicePlan(
            dependencies=dependencies,
            property_dependencies=_cached_property_dependencies(cast(Any, cls)),
        )
        registration.plan = plan
        return plan

    def _get_factory_plan(self, registration: Registration) -> _FactoryPlan:
        if registration.plan is not None:
            return registration.plan  # type: ignore[return-value]

        factory = registration.factory
        if factory is None:
            raise ValueError("Factory cannot be None for factory registration.")

        plan = _FactoryPlan(dependencies=_get_callable_plan(factory).dependencies)
        registration.plan = plan
        return plan

    @staticmethod
    def _describe_owner(owner: Any, name: str) -> str:
        return f"{getattr(owner, '__name__', owner)}.{name}"

    @staticmethod
    def _describe_dependency(dependency_plan: _DependencyPlan) -> str:
        detail = _describe_service(dependency_plan.dependency_type)
        key = dependency_plan.dependency_key
        if key is not None and key[1] is not None:
            detail += f" named '{key[1]}'"
        return detail

    def _resolve_dependency_plan(
        self, dependency_plan: _DependencyPlan, scope: Scope, owner: Any
    ) -> Any:
        if dependency_plan.inject_container:
            return self

        dependency_type = dependency_plan.dependency_type
        if dependency_type == inspect.Parameter.empty:
            raise MissingTypeAnnotationException(dependency_plan.name, owner)

        if dependency_type in self._resolving:
            raise CyclicDependencyException(dependency_type)

        dependency_key = dependency_plan.dependency_key
        registrations = None
        if dependency_key is not None:
            registrations = self._registrations.get(dependency_key)
        if registrations:
            registration = registrations[0]
            key = dependency_key
            if registration.kind == RegistrationType.INSTANCE:
                return registration.instance

            instance_key = (key, registration)
            lifestyle = registration.lifestyle
            if lifestyle == LifeStyle.SINGLETON:
                existing = self._singletons.get(instance_key, _MISSING)
                if existing is not _MISSING:
                    return existing
                return self._get_or_create_singleton(instance_key, registration, scope)
            if lifestyle == LifeStyle.SCOPED:
                if instance_key in scope._scoped_instances:
                    return scope._scoped_instances[instance_key]
                instance = self._create_instance_from_registration(registration, scope)
                scope._scoped_instances[instance_key] = instance
                return instance
            return self._create_instance_from_registration(registration, scope)

        if dependency_plan.has_default:
            return dependency_plan.default
        if dependency_plan.is_optional:
            return None
        raise ServiceNotRegisteredException(
            self._describe_dependency(dependency_plan),
            required_by=self._describe_owner(owner, dependency_plan.name),
        )

    def _invoke_factory_registration(
        self, registration: Registration, scope: Scope
    ) -> Any:
        factory = registration.factory
        if factory is None:
            raise ValueError("Factory cannot be None for factory registration.")
        if registration.is_async or registration.is_resource:
            raise AsyncResolutionRequiredException(factory)
        plan = self._get_factory_plan(registration)
        args = [
            self._resolve_dependency_plan(dependency_plan, scope, factory)
            for dependency_plan in plan.dependencies
        ]
        if registration.is_sync_resource:
            # Generator factory used as a resource: enter its context on the
            # singleton's container stack (closed by close()) or the scope's stack
            # (closed when the scope exits), so teardown runs after the yield.
            cm = contextmanager(factory)(*args)
            if registration.lifestyle == LifeStyle.SINGLETON:
                return self._get_sync_stack().enter_context(cm)
            return scope._stack.enter_context(cm)
        return factory(*args)

    def _get_sync_stack(self) -> ExitStack:
        if self._sync_stack is None:
            self._sync_stack = ExitStack()
        return self._sync_stack

    def close(self) -> None:
        """Finalize singleton sync resources. Call once at application shutdown
        (or use the container as a context manager)."""
        if self._sync_stack is not None:
            stack, self._sync_stack = self._sync_stack, None
            for instance_key in self._sync_resource_keys:
                self._singletons.pop(instance_key, None)
            self._sync_resource_keys.clear()
            stack.close()

    # ------------------------------------------------------------------ async

    def ascope(self) -> AsyncScope:
        """Open an async resolution scope. Use as ``async with``; async resources
        resolved inside are finalized when the block exits."""
        return AsyncScope(self)

    async def acall(self, func: Callable[..., Any], /, **overrides: Any) -> Any:
        """Async counterpart of :meth:`call`. Awaits async dependencies, awaits
        ``func`` if it is a coroutine function, and finalizes any async resources
        opened for the call when it returns."""
        plan = _get_callable_plan(func)
        async with self.ascope() as scope:
            kwargs: dict[str, Any] = dict(overrides)
            for dependency_plan in plan.dependencies:
                if dependency_plan.name in overrides:
                    continue
                if dependency_plan.inject_container:
                    kwargs[dependency_plan.name] = self
                else:
                    kwargs[dependency_plan.name] = await self._aresolve_dependency_plan(
                        dependency_plan, scope, func, set()
                    )
            result = func(**kwargs)
            if inspect.isawaitable(result):
                result = await result
            return result

    @overload
    async def aresolve(self, interface: type[T], name: str | None = None) -> T: ...
    @overload
    async def aresolve(self, interface: str, name: str | None = None) -> Any: ...
    async def aresolve(self, interface: type | str, name: str | None = None) -> Any:
        """Resolve a service through the async path (awaits async factories).

        Convenience wrapper that opens a short-lived scope. Singleton resources
        live until ``await container.aclose()``; scoped/transient resources must
        be resolved inside ``async with container.ascope()`` instead, since the
        short-lived scope here would finalize them before you could use them.
        """
        if name is None:
            # Fully-sync graph (no factories anywhere): reuse the compiled sync
            # creator and skip allocating an async scope + coroutine walk. This
            # is the common FastAPI case — await aresolve() on plain classes.
            try:
                creator = self._noscope_creators[interface]
            except KeyError:
                creator = self._prime_noscope_creator(interface)
            if creator is not None:
                return creator(None)
        acreator = self._get_async_creator(interface, name)
        if acreator is not None:
            creator_fn, creator_needs_scope = acreator
            if not creator_needs_scope:
                # Singletons only: no scope to allocate or finalize, and a
                # top-level transient/scoped resource always needs a scope, so
                # the resource footgun cannot apply here — skip the guard lookup.
                return await creator_fn(None)
            self._guard_top_async_resource(interface, name)
            async with self.ascope() as scope:
                return await creator_fn(scope)
        self._guard_top_async_resource(interface, name)
        async with self.ascope() as scope:
            return await scope.aresolve(interface, name)

    def _guard_top_async_resource(
        self, interface: type | str, name: str | None
    ) -> None:
        registrations = self._registrations.get((interface, name))
        if registrations:
            registration = registrations[0]
            if registration.is_resource and registration.lifestyle in (
                LifeStyle.TRANSIENT,
                LifeStyle.SCOPED,
            ):
                raise ValueError(
                    f"{interface} is a {registration.lifestyle} async resource; "
                    "aresolve() would finalize it immediately. Resolve it inside "
                    "'async with container.ascope() as scope: "
                    "await scope.aresolve(...)'."
                )

    async def aclose(self) -> None:
        """Finalize singleton async resources. Call once at application shutdown."""
        if self._async_stack is not None:
            stack, self._async_stack = self._async_stack, None
            # Evict the finalized singleton resources so a later resolve rebuilds
            # them instead of handing back a closed object.
            for instance_key in self._async_resource_keys:
                self._singletons.pop(instance_key, None)
            self._async_resource_keys.clear()
            await stack.aclose()

    def _get_async_stack(self) -> AsyncExitStack:
        if self._async_stack is None:
            self._async_stack = AsyncExitStack()
        return self._async_stack

    async def _aresolve_one(
        self,
        interface: type | str,
        scope: AsyncScope,
        name: str | None,
        resolving: set[Any],
    ) -> Any:
        key = (interface, name)
        registrations = self._registrations.get(key)
        if not registrations:
            interface_name = _describe_service(interface)
            if name is not None:
                interface_name += f" with name '{name}'"
            raise ServiceNotRegisteredException(interface_name)
        return await self._aget_instance_from_registration(
            registrations[0], scope, key, resolving
        )

    async def _aget_instance_from_registration(
        self,
        registration: Registration,
        scope: AsyncScope,
        key: tuple[type | str, str | None],
        resolving: set[Any],
    ) -> Any:
        if registration.kind == RegistrationType.INSTANCE:
            return registration.instance

        instance_key = (key, registration)
        lifestyle = registration.lifestyle
        if lifestyle == LifeStyle.SINGLETON:
            existing = self._singletons.get(instance_key, _MISSING)
            if existing is not _MISSING:
                return existing
            return await self._aget_or_create_singleton(
                instance_key, registration, scope, resolving
            )
        if lifestyle == LifeStyle.SCOPED:
            if instance_key in scope._scoped_instances:
                return scope._scoped_instances[instance_key]
            instance = await self._acreate_instance_from_registration(
                registration, scope, resolving, singleton=False
            )
            scope._scoped_instances[instance_key] = instance
            return instance
        return await self._acreate_instance_from_registration(
            registration, scope, resolving, singleton=False
        )

    async def _aget_or_create_singleton(
        self,
        instance_key: Any,
        registration: Registration,
        scope: AsyncScope,
        resolving: set[Any],
    ) -> Any:
        # asyncio is single-threaded, so reserving the in-flight task before the
        # first await is atomic: a coroutine that arrives while a build is pending
        # awaits the same task instead of starting its own.
        pending = self._async_inflight.get(instance_key)
        task: asyncio.Future[Any]
        if pending is None:
            task = asyncio.ensure_future(
                self._acreate_instance_from_registration(
                    registration, scope, resolving, singleton=True
                )
            )
            self._async_inflight[instance_key] = task
            owner = True
        else:
            task = pending
            owner = False
        try:
            instance = await task
        finally:
            if owner:
                self._async_inflight.pop(instance_key, None)
        if owner:
            self._singletons[instance_key] = instance
            if registration.is_resource:
                self._async_resource_keys.add(instance_key)
        return instance

    async def _acreate_instance_from_registration(
        self,
        registration: Registration,
        scope: AsyncScope,
        resolving: set[Any],
        singleton: bool,
    ) -> Any:
        if registration.kind == RegistrationType.SERVICE:
            if registration.implementation is None:
                raise ValueError(
                    "Implementation cannot be None for service registration."
                )
            return await self._acreate_service_from_registration(
                registration, scope, resolving
            )
        if registration.kind == RegistrationType.FACTORY:
            if registration.factory is None:
                raise ValueError("Factory cannot be None for factory registration.")
            return await self._ainvoke_factory_registration(
                registration, scope, resolving, singleton
            )
        raise ValueError(f"Invalid registration kind: {registration.kind}")

    async def _acreate_service_from_registration(
        self, registration: Registration, scope: AsyncScope, resolving: set[Any]
    ) -> Any:
        cls = registration.implementation
        if cls is None:
            raise ValueError("Implementation cannot be None for service registration.")
        if cls in resolving:
            raise CyclicDependencyException(cls)

        plan = self._get_service_plan(registration)
        resolving.add(cls)
        try:
            if plan.dependencies:
                args = [
                    await self._aresolve_dependency_plan(
                        dependency_plan, scope, cls, resolving
                    )
                    for dependency_plan in plan.dependencies
                ]
                instance = cls(*args)
            else:
                instance = cls()
            if plan.property_dependencies:
                await self._ainject_property_dependencies(
                    instance, scope, plan.property_dependencies, resolving
                )
            return instance
        finally:
            resolving.discard(cls)

    async def _ainvoke_factory_registration(
        self,
        registration: Registration,
        scope: AsyncScope,
        resolving: set[Any],
        singleton: bool,
    ) -> Any:
        factory = registration.factory
        if factory is None:
            raise ValueError("Factory cannot be None for factory registration.")
        plan = self._get_factory_plan(registration)
        args = [
            await self._aresolve_dependency_plan(
                dependency_plan, scope, factory, resolving
            )
            for dependency_plan in plan.dependencies
        ]
        if registration.is_resource:
            stack = self._get_async_stack() if singleton else scope._stack
            cm = asynccontextmanager(factory)(*args)
            return await stack.enter_async_context(cm)
        if registration.is_async:
            return await factory(*args)
        return factory(*args)

    async def _aresolve_dependency_plan(
        self,
        dependency_plan: _DependencyPlan,
        scope: AsyncScope,
        owner: Any,
        resolving: set[Any],
    ) -> Any:
        if dependency_plan.inject_container:
            return self

        dependency_type = dependency_plan.dependency_type
        if dependency_type == inspect.Parameter.empty:
            raise MissingTypeAnnotationException(dependency_plan.name, owner)
        if dependency_type in resolving:
            raise CyclicDependencyException(dependency_type)

        dependency_key = dependency_plan.dependency_key
        registrations = None
        if dependency_key is not None:
            registrations = self._registrations.get(dependency_key)
        if registrations and dependency_key is not None:
            return await self._aget_instance_from_registration(
                registrations[0], scope, dependency_key, resolving
            )

        if dependency_plan.has_default:
            return dependency_plan.default
        if dependency_plan.is_optional:
            return None
        raise ServiceNotRegisteredException(
            self._describe_dependency(dependency_plan),
            required_by=self._describe_owner(owner, dependency_plan.name),
        )

    async def _ainject_property_dependencies(
        self,
        instance: object,
        scope: AsyncScope,
        property_dependencies: tuple[_DependencyPlan, ...],
        resolving: set[Any],
    ) -> None:
        existing = getattr(instance, "__dict__", None)
        for dependency_plan in property_dependencies:
            if existing is not None and dependency_plan.name in existing:
                continue
            dependency_type = dependency_plan.dependency_type
            if dependency_type in resolving:
                raise CyclicDependencyException(dependency_type)
            dependency = await self._aresolve_dependency_plan(
                dependency_plan, scope, type(instance), resolving
            )
            try:
                setattr(instance, dependency_plan.name, dependency)
            except AttributeError as exc:
                raise PropertyInjectionException(
                    type(instance), dependency_plan.name
                ) from exc

    def _inject_property_dependencies(
        self,
        instance: object,
        scope: Scope,
        property_dependencies: tuple[_DependencyPlan, ...],
    ) -> None:
        # `__dict__` is absent on __slots__ types; getattr keeps the
        # "already set?" check working without raising on those.
        existing = getattr(instance, "__dict__", None)
        for dependency_plan in property_dependencies:
            if existing is not None and dependency_plan.name in existing:
                continue
            dependency_type = dependency_plan.dependency_type
            if dependency_type in self._resolving:
                raise CyclicDependencyException(dependency_type)

            dependency = self._resolve_dependency_plan(
                dependency_plan, scope, type(instance)
            )

            try:
                setattr(instance, dependency_plan.name, dependency)
            except AttributeError as exc:
                # __slots__ without the slot, or a frozen dataclass
                # (FrozenInstanceError subclasses AttributeError).
                raise PropertyInjectionException(
                    type(instance), dependency_plan.name
                ) from exc

    def _create_service_from_registration(
        self, registration: Registration, scope: Scope
    ) -> Any:
        cls = registration.implementation
        if cls is None:
            raise ValueError("Implementation cannot be None for service registration.")
        if cls in self._resolving:
            raise CyclicDependencyException(cls)

        plan = self._get_service_plan(registration)
        self._resolving.add(cls)
        try:
            if plan.dependencies:
                args = [
                    self._resolve_dependency_plan(dependency_plan, scope, cls)
                    for dependency_plan in plan.dependencies
                ]
                instance = cls(*args)
            else:
                instance = cls()
            if plan.property_dependencies:
                self._inject_property_dependencies(
                    instance, scope, plan.property_dependencies
                )
            return instance
        finally:
            self._resolving.discard(cls)

    def add_singleton(
        self,
        interface: type,
        implementation: type | None = None,
        name: str | None = None,
    ) -> None:
        """Register a class created once and shared (singleton)."""
        self.register(
            interface, implementation, lifestyle=LifeStyle.SINGLETON, name=name
        )

    def add_transient(
        self,
        interface: type,
        implementation: type | None = None,
        name: str | None = None,
    ) -> None:
        """Register a class created fresh on every resolve (transient)."""
        self.register(
            interface, implementation, lifestyle=LifeStyle.TRANSIENT, name=name
        )

    def add_scoped(
        self,
        interface: type,
        implementation: type | None = None,
        name: str | None = None,
    ) -> None:
        """Register a class created once per scope (scoped)."""
        self.register(interface, implementation, lifestyle=LifeStyle.SCOPED, name=name)

    def add_singleton_factory(
        self,
        interface: type,
        factory: Callable[..., Any],
        name: str | None = None,
    ) -> None:
        """Register a factory whose result is built once and shared (singleton)."""
        self.register_factory(
            interface, factory, lifestyle=LifeStyle.SINGLETON, name=name
        )

    def add_transient_factory(
        self,
        interface: type,
        factory: Callable[..., Any],
        name: str | None = None,
    ) -> None:
        """Register a factory invoked on every resolve (transient)."""
        self.register_factory(
            interface, factory, lifestyle=LifeStyle.TRANSIENT, name=name
        )

    def add_scoped_factory(
        self,
        interface: type,
        factory: Callable[..., Any],
        name: str | None = None,
    ) -> None:
        """Register a factory invoked once per scope (scoped). Async-generator
        factories yield a scoped resource finalized when the scope exits."""
        self.register_factory(interface, factory, lifestyle=LifeStyle.SCOPED, name=name)
