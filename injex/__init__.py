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
    get_args,
    get_origin,
    get_type_hints,
)


class DIException(Exception):
    """Base exception class for dependency injection errors."""


class ServiceNotRegisteredException(DIException):
    def __init__(self, interface_description: str):
        super().__init__(
            f"Service for interface '{interface_description}' is not registered."
        )


class CyclicDependencyException(DIException):
    def __init__(self, cls: Type):
        super().__init__(f"Cyclic dependency detected: {cls}.")


class MissingTypeAnnotationException(DIException):
    def __init__(self, param_name: str, cls: Type):
        super().__init__(
            f"Missing type annotation for parameter '{param_name}' in class '{cls.__name__}'."
        )


class InvalidLifestyleException(DIException):
    def __init__(self, lifestyle: str):
        super().__init__(
            f"Invalid lifestyle '{lifestyle}'. Valid options are 'transient' or 'singleton'."
        )


def inject(func: Callable) -> Callable:
    func.__annotations__["_inject"] = True
    return func


def is_injectable(func: Callable) -> bool:
    return hasattr(func, "__annotations__") and func.__annotations__.get(
        "_inject", False
    )


class LifeStyle:
    TRANSIENT = "transient"
    SINGLETON = "singleton"
    SCOPED = "scoped"


class RegistrationType:
    SERVICE = "service"
    FACTORY = "factory"
    INSTANCE = "instance"


class Scope:
    __slots__ = ("container", "_scoped_instances")

    def __init__(self, container: "Container"):
        self.container = container
        self._scoped_instances: Dict[Any, Any] = {}

    def resolve(self, interface: Union[Type, str], name: Optional[str] = None) -> Any:
        instances = self.container._resolve_in_scope(interface, self, name)
        if not instances:
            interface_name = f"{interface}"
            if name is not None:
                interface_name += f" with name '{name}'"
            raise ServiceNotRegisteredException(interface_name)
        return instances[0]

    def resolve_all(
        self, interface: Union[Type, str], name: Optional[str] = None
    ) -> List[Any]:
        return self.container._resolve_in_scope(interface, self, name)


class Registration:
    def __init__(
        self,
        kind: str,  # registration type
        implementation: Optional[Type] = None,
        factory: Optional[Callable[..., Any]] = None,
        instance: Optional[Any] = None,
        lifestyle: str = LifeStyle.TRANSIENT,
    ):
        self.kind = kind
        self.implementation = implementation
        self.factory = factory
        self.instance = instance
        self.lifestyle = lifestyle


class OverrideContext:
    def __init__(
        self,
        container: "Container",
        key: Tuple[Union[Type, str], Optional[str]],
        registration: Registration,
    ):
        self.container = container
        self.key = key
        self.registration = registration
        self._previous_registrations: Optional[List[Registration]] = None
        self._previous_singletons: Dict[Any, Any] = {}

    def __enter__(self) -> "Container":
        self._previous_registrations = list(
            self.container._registrations.get(self.key, [])
        )
        self._previous_singletons = self.container._pop_singletons_for_key(self.key)
        self.container._registrations[self.key] = [self.registration]
        return self.container

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.container._pop_singletons_for_key(self.key)
        if self._previous_registrations:
            self.container._registrations[self.key] = self._previous_registrations
        else:
            self.container._registrations.pop(self.key, None)
        self.container._singletons.update(self._previous_singletons)


class Container:
    __slots__ = ("_registrations", "_singletons", "_resolving")

    def __init__(self):
        self._registrations: Dict[
            Tuple[Union[Type, str], Optional[str]], List[Registration]
        ] = {}
        self._singletons: Dict[Any, Any] = {}
        self._resolving: Set[Type] = set()

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
        scope = self.create_scope()
        return scope.resolve(interface, name)

    def resolve_all(
        self, interface: Union[Type, str], name: Optional[str] = None
    ) -> List[Any]:
        scope = self.create_scope()
        return scope.resolve_all(interface, name)

    def create_scope(self) -> Scope:
        return Scope(self)

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

    def _get_instance_from_registration(
        self,
        registration: Registration,
        scope: Scope,
        key: Tuple[Union[Type, str], Optional[str]],
    ) -> Any:
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
                return self._create_instance(registration.implementation, scope)
            else:
                raise ValueError(
                    "Implementation cannot be None for service registration."
                )
        elif registration.kind == RegistrationType.FACTORY:
            if registration.factory is not None:
                return self._invoke_factory(registration.factory, scope)
            else:
                raise ValueError("Factory cannot be None for factory registration.")
        else:
            raise ValueError(f"Invalid registration kind: {registration.kind}")

    def _invoke_factory(self, factory: Callable[..., Any], scope: Scope) -> Any:
        sig = inspect.signature(factory)
        params = sig.parameters
        args = []
        for name, param in params.items():
            if param.annotation == inspect.Parameter.empty:
                if name == "container":
                    dependency = self
                else:
                    raise MissingTypeAnnotationException(name, factory)  # type: ignore
            else:
                param_annotation = param.annotation

                is_optional = False
                origin = get_origin(param_annotation)
                if origin in (Union, types.UnionType):
                    args_ = get_args(param_annotation)
                    if type(None) in args_:
                        is_optional = True
                        non_none_args = [a for a in args_ if a is not type(None)]
                        if non_none_args:
                            param_annotation = non_none_args[0]
                        else:
                            param_annotation = Any

                try:
                    dependency = scope.resolve(param_annotation)  # type: ignore
                except ServiceNotRegisteredException:
                    if param.default != inspect.Parameter.empty:
                        dependency = param.default
                    elif is_optional:
                        dependency = None
                    else:
                        raise
            args.append(dependency)
        return factory(*args)

    def _inject_properties(self, instance: object, scope: Scope) -> None:
        for name in dir(instance):
            attr = getattr(instance, name)
            if callable(attr) and is_injectable(attr):
                if name in instance.__dict__:
                    continue
                type_hints = get_type_hints(attr)
                if (
                    "return" in type_hints
                    and type_hints["return"] != inspect.Parameter.empty
                ):
                    dependency_type = type_hints["return"]

                    if dependency_type in self._resolving:
                        raise CyclicDependencyException(dependency_type)

                    try:
                        dependency = scope.resolve(dependency_type)
                    except ServiceNotRegisteredException as e:
                        raise e

                    setattr(instance, name, dependency)

    def _create_instance(self, cls: Type, scope: Scope) -> Any:
        if cls in self._resolving:
            raise CyclicDependencyException(cls)

        self._resolving.add(cls)
        try:
            constructor = cls.__init__
            if constructor is object.__init__:
                instance = cls()
            else:
                type_hints = get_type_hints(constructor)
                params = inspect.signature(constructor).parameters
                args = []
                for name, param in params.items():
                    if name == "self":
                        continue
                    param_annotation = type_hints.get(name, param.annotation)

                    is_optional = False
                    origin = get_origin(param_annotation)
                    if origin in (Union, types.UnionType):
                        args_ = get_args(param_annotation)
                        if type(None) in args_:
                            is_optional = True
                            non_none_args = [a for a in args_ if a is not type(None)]
                            if non_none_args:
                                param_annotation = non_none_args[0]
                            else:
                                param_annotation = Any

                    if param_annotation == inspect.Parameter.empty:
                        raise MissingTypeAnnotationException(name, cls)

                    if param_annotation in self._resolving:
                        raise CyclicDependencyException(param_annotation)

                    try:
                        dependency = scope.resolve(param_annotation)  # type: ignore
                    except ServiceNotRegisteredException:
                        if param.default != inspect.Parameter.empty:
                            dependency = param.default
                        elif is_optional:
                            dependency = None
                        else:
                            raise
                    args.append(dependency)
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
