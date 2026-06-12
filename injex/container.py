import inspect
import types
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
    cast,
    get_args,
    get_origin,
)

from .errors import (
    ContainerValidationException,
    CyclicDependencyException,
    InvalidLifestyleException,
    MissingTypeAnnotationException,
    ServiceNotRegisteredException,
    ValidationError,
    _describe_service,
)
from .planning import (
    _DependencyPlan,
    _FactoryPlan,
    _ServicePlan,
    _cached_injected_properties,
    _cached_property_dependencies,
    _cached_type_hints,
    _get_callable_plan,
    _get_parameters,
    _get_type_hints,
    _make_constant_creator,
    _make_fast_raw_creator,
    _none_creator,
)
from .registry import LifeStyle, OverrideContext, Registration, RegistrationType

_MISSING = object()


class _NotFlat(Exception):
    """Raised internally when a graph cannot be compiled to a flat creator."""


class Scope:
    __slots__ = ("container", "_scoped_instances")

    def __init__(self, container: "Container"):
        self.container = container
        self._scoped_instances: Dict[Any, Any] = {}

    def resolve(self, interface: Union[Type, str], name: Optional[str] = None) -> Any:
        return self.container._resolve_one(interface, self, name)

    def resolve_all(
        self, interface: Union[Type, str], name: Optional[str] = None
    ) -> List[Any]:
        return self.container._resolve_in_scope(interface, self, name)


class Container:
    __slots__ = (
        "_registrations",
        "_singletons",
        "_resolving",
        "_version",
        "_noscope_creators",
    )

    def __init__(self):
        self._registrations: Dict[
            Tuple[Union[Type, str], Optional[str]], List[Registration]
        ] = {}
        self._singletons: Dict[Any, Any] = {}
        self._resolving: Set[Type] = set()
        self._version = 0
        # Direct interface -> creator dispatch for the common name=None,
        # no-scope-needed case. Skips the per-resolve key-tuple allocation and
        # registration attribute reads. Value is None when the interface is not
        # eligible for the no-scope fast path. Cleared on every invalidation.
        self._noscope_creators: Dict[Any, Optional[Callable[[Any], Any]]] = {}

    def _invalidate_fast_creators(self) -> None:
        self._version += 1
        self._noscope_creators.clear()

    def register(
        self,
        interface: Type,
        implementation: Optional[Type] = None,
        lifestyle: str = LifeStyle.TRANSIENT,
        name: Optional[str] = None,
    ) -> None:
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
        interface: Type,
        factory: Callable[..., Any],
        lifestyle: str = LifeStyle.TRANSIENT,
        name: Optional[str] = None,
    ) -> None:
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
        self._registrations.setdefault(key, []).append(registration)
        self._invalidate_fast_creators()

    def add_instance(
        self, interface: Type, instance: Any, name: Optional[str] = None
    ) -> None:
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
        interface: Type,
        implementation: Optional[Type] = None,
        *,
        factory: Optional[Callable[..., Any]] = None,
        instance: Optional[Any] = None,
        lifestyle: str = LifeStyle.TRANSIENT,
        name: Optional[str] = None,
    ) -> OverrideContext:
        provided = sum(
            value is not None for value in (implementation, factory, instance)
        )
        if provided > 1:
            raise ValueError(
                "Provide only one override target: implementation, factory, or instance."
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
        self, key: Tuple[Union[Type, str], Optional[str]]
    ) -> Dict[Any, Any]:
        removed = {}
        for instance_key in list(self._singletons):
            if instance_key[0] == key:
                removed[instance_key] = self._singletons.pop(instance_key)
        return removed

    def resolve(self, interface: Union[Type, str], name: Optional[str] = None) -> Any:
        if name is None:
            creator = self._noscope_creators.get(interface, _MISSING)
            if creator is _MISSING:
                creator = self._prime_noscope_creator(interface)
            if creator is not None:
                return creator(None)  # type: ignore[operator]
            scope = Scope(self)
            return self._resolve_one(interface, scope, None)
        return self._resolve_slow(interface, name)

    def _prime_noscope_creator(
        self, interface: Union[Type, str]
    ) -> Optional[Callable[[Any], Any]]:
        creator: Optional[Callable[[Any], Any]] = None
        registrations = self._registrations.get((interface, None))
        if registrations:
            registration = registrations[0]
            self._get_fast_creator(registration, (interface, None))
            if (
                registration.fast_creator is not None
                and not registration.fast_creator_needs_scope
            ):
                creator = registration.fast_creator
        self._noscope_creators[interface] = creator
        return creator

    def _resolve_slow(self, interface: Union[Type, str], name: Optional[str]) -> Any:
        key = (interface, name)
        registrations = self._registrations.get(key)
        if registrations:
            registration = registrations[0]
            if registration.fast_creator_version != self._version:
                self._get_fast_creator(registration, key)
            fast_creator = registration.fast_creator
            if fast_creator is not None and not registration.fast_creator_needs_scope:
                return fast_creator(None)  # type: ignore[arg-type]
        scope = self.create_scope()
        return self._resolve_one(interface, scope, name)

    def resolve_all(
        self, interface: Union[Type, str], name: Optional[str] = None
    ) -> List[Any]:
        scope = self.create_scope()
        return scope.resolve_all(interface, name)

    def create_scope(self) -> Scope:
        return Scope(self)

    def validate(self) -> List[ValidationError]:
        """Validate registered dependency graphs without creating service instances."""
        errors: List[ValidationError] = []
        for key, registrations in self._registrations.items():
            for registration in registrations:
                errors.extend(self._validate_registration(key, registration, []))
        return errors

    def assert_valid(self) -> None:
        """Raise ContainerValidationException when any registration is invalid."""
        errors = self.validate()
        if errors:
            raise ContainerValidationException(errors)

    def _resolve_in_scope(
        self, interface: Union[Type, str], scope: Scope, name: Optional[str] = None
    ) -> List[Any]:
        key = (interface, name)
        registrations = self._registrations.get(key, [])
        instances = []
        for registration in registrations:
            instance = self._get_instance_from_registration(registration, scope, key)
            instances.append(instance)
        return instances

    def _resolve_one(
        self, interface: Union[Type, str], scope: Scope, name: Optional[str] = None
    ) -> Any:
        key = (interface, name)
        registrations = self._registrations.get(key)
        if not registrations:
            interface_name = f"{interface}"
            if name is not None:
                interface_name += f" with name '{name}'"
            raise ServiceNotRegisteredException(interface_name)
        return self._get_instance_from_registration(registrations[0], scope, key)

    def _validate_registration(
        self,
        key: Tuple[Union[Type, str], Optional[str]],
        registration: Registration,
        path: List[Tuple[Union[Type, str], Optional[str]]],
    ) -> List[ValidationError]:
        if registration.kind == RegistrationType.INSTANCE:
            return []

        if key in path:
            cycle = path + [key]
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
            return self._validate_class(registration.implementation, key, path + [key])

        if registration.kind == RegistrationType.FACTORY:
            if registration.factory is None:
                return [
                    ValidationError(key[0], key[1], "Factory registration is empty.")
                ]
            return self._validate_callable(registration.factory, key, path + [key])

        return [ValidationError(key[0], key[1], "Registration kind is not supported.")]

    def _validate_class(
        self,
        cls: Type,
        source_key: Tuple[Union[Type, str], Optional[str]],
        path: List[Tuple[Union[Type, str], Optional[str]]],
    ) -> List[ValidationError]:
        errors: List[ValidationError] = []
        constructor = cls.__init__
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
        source_key: Tuple[Union[Type, str], Optional[str]],
        path: List[Tuple[Union[Type, str], Optional[str]]],
        skip_self: bool = False,
    ) -> List[ValidationError]:
        errors: List[ValidationError] = []
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
        source_key: Tuple[Union[Type, str], Optional[str]],
        path: List[Tuple[Union[Type, str], Optional[str]]],
        dependency_name: str,
        has_default: bool = False,
    ) -> List[ValidationError]:
        is_optional = False
        origin = get_origin(dependency_type)
        if origin in (Union, types.UnionType):
            args = get_args(dependency_type)
            if type(None) in args:
                is_optional = True
                non_none_args = [arg for arg in args if arg is not type(None)]
                dependency_type = non_none_args[0] if non_none_args else Any

        dependency_key = self._get_validation_key(dependency_type)
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

        errors: List[ValidationError] = []
        for registration in registrations:
            errors.extend(
                self._validate_registration(dependency_key, registration, path)
            )
        return errors

    def _get_validation_key(
        self, dependency_type: Any
    ) -> Tuple[Union[Type, str], None]:
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
        key: Tuple[Union[Type, str], Optional[str]],
    ) -> Optional[Callable[[Scope], Any]]:
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
        key: Tuple[Union[Type, str], Optional[str]],
    ) -> Optional[Tuple[Callable[[Any], Any], bool]]:
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

        namespace: Dict[str, Any] = {}
        prelude: List[str] = []
        shared: Dict[Any, str] = {}
        counter = [0]
        needs_scope = [False]

        def bind(obj: Any, prefix: str) -> str:
            counter[0] += 1
            sym = f"{prefix}{counter[0]}"
            namespace[sym] = obj
            return sym

        def emit(
            reg: Registration,
            node_key: Tuple[Union[Type, str], Optional[str]],
            path: frozenset,
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
            child_exprs: List[str] = []
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
        local: Dict[str, Any] = {}
        exec("\n".join(source_lines), namespace, local)  # noqa: S102
        return local["_flat"], needs_scope[0]

    def _build_fast_creator(
        self,
        registration: Registration,
        key: Tuple[Union[Type, str], Optional[str]],
        path: Set[Tuple[Union[Type, str], Optional[str]]],
    ) -> Optional[Tuple[Callable[[Scope], Any], bool]]:
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
        dependency_creators: List[Callable[[Scope], Any]] = []
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

            def create_singleton(scope: Scope) -> Any:
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

    def _get_instance_from_registration(
        self,
        registration: Registration,
        scope: Scope,
        key: Tuple[Union[Type, str], Optional[str]],
    ) -> Any:
        fast_creator = self._get_fast_creator(registration, key)
        if fast_creator is not None:
            return fast_creator(scope)

        instance_key = (key, registration)
        if registration.kind == RegistrationType.INSTANCE:
            return registration.instance

        lifestyle = registration.lifestyle

        if lifestyle == LifeStyle.SINGLETON:
            if instance_key in self._singletons:
                return self._singletons[instance_key]
            instance = self._create_instance_from_registration(registration, scope)
            self._singletons[instance_key] = instance
            return instance
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

        constructor = cls.__init__
        dependencies: Tuple[_DependencyPlan, ...] = ()
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

    def _resolve_dependency_plan(
        self, dependency_plan: _DependencyPlan, scope: Scope, owner: Type
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
                if instance_key in self._singletons:
                    return self._singletons[instance_key]
                instance = self._create_instance_from_registration(registration, scope)
                self._singletons[instance_key] = instance
                return instance
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
        raise ServiceNotRegisteredException(f"{dependency_type}")

    def _invoke_factory_registration(
        self, registration: Registration, scope: Scope
    ) -> Any:
        factory = registration.factory
        if factory is None:
            raise ValueError("Factory cannot be None for factory registration.")
        plan = self._get_factory_plan(registration)
        args = [
            self._resolve_dependency_plan(dependency_plan, scope, factory)  # type: ignore[arg-type]
            for dependency_plan in plan.dependencies
        ]
        return factory(*args)

    def _inject_property_dependencies(
        self,
        instance: object,
        scope: Scope,
        property_dependencies: Tuple[_DependencyPlan, ...],
    ) -> None:
        for dependency_plan in property_dependencies:
            if dependency_plan.name in instance.__dict__:
                continue
            dependency_type = dependency_plan.dependency_type
            if dependency_type in self._resolving:
                raise CyclicDependencyException(dependency_type)

            dependency = self._resolve_dependency_plan(
                dependency_plan, scope, type(instance)
            )

            setattr(instance, dependency_plan.name, dependency)

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
            self._resolving.remove(cls)

    def _invoke_factory(self, factory: Callable[..., Any], scope: Scope) -> Any:
        plan = _get_callable_plan(factory)
        args = [
            self._resolve_dependency_plan(dependency_plan, scope, factory)  # type: ignore[arg-type]
            for dependency_plan in plan.dependencies
        ]
        return factory(*args)

    def _inject_properties(self, instance: object, scope: Scope) -> None:
        for dependency_plan in _cached_property_dependencies(cast(Any, type(instance))):
            if dependency_plan.name in instance.__dict__:
                continue
            dependency_type = dependency_plan.dependency_type
            if dependency_type in self._resolving:
                raise CyclicDependencyException(dependency_type)

            dependency = self._resolve_dependency_plan(
                dependency_plan, scope, type(instance)
            )

            setattr(instance, dependency_plan.name, dependency)

    def _create_instance(self, cls: Type, scope: Scope) -> Any:
        if cls in self._resolving:
            raise CyclicDependencyException(cls)

        self._resolving.add(cls)
        try:
            constructor = cls.__init__
            if constructor is object.__init__:
                instance = cls()
            else:
                plan = _get_callable_plan(constructor, skip_self=True)
                args = [
                    self._resolve_dependency_plan(dependency_plan, scope, cls)
                    for dependency_plan in plan.dependencies
                ]
                instance = cls(*args)
            self._inject_properties(instance, scope)
            return instance
        finally:
            self._resolving.remove(cls)

    def add_singleton(
        self,
        interface: Type,
        implementation: Optional[Type] = None,
        name: Optional[str] = None,
    ) -> None:
        self.register(
            interface, implementation, lifestyle=LifeStyle.SINGLETON, name=name
        )

    def add_transient(
        self,
        interface: Type,
        implementation: Optional[Type] = None,
        name: Optional[str] = None,
    ) -> None:
        self.register(
            interface, implementation, lifestyle=LifeStyle.TRANSIENT, name=name
        )

    def add_scoped(
        self,
        interface: Type,
        implementation: Optional[Type] = None,
        name: Optional[str] = None,
    ) -> None:
        self.register(interface, implementation, lifestyle=LifeStyle.SCOPED, name=name)

    def add_singleton_factory(
        self,
        interface: Type,
        factory: Callable[..., Any],
        name: Optional[str] = None,
    ) -> None:
        self.register_factory(
            interface, factory, lifestyle=LifeStyle.SINGLETON, name=name
        )

    def add_transient_factory(
        self,
        interface: Type,
        factory: Callable[..., Any],
        name: Optional[str] = None,
    ) -> None:
        self.register_factory(
            interface, factory, lifestyle=LifeStyle.TRANSIENT, name=name
        )

    def add_scoped_factory(
        self,
        interface: Type,
        factory: Callable[..., Any],
        name: Optional[str] = None,
    ) -> None:
        self.register_factory(interface, factory, lifestyle=LifeStyle.SCOPED, name=name)
