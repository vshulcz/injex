import inspect
import types
from dataclasses import dataclass
from functools import lru_cache
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)


def inject(func: Callable) -> Callable:
    func.__annotations__["_inject"] = True
    return func


def is_injectable(func: Callable) -> bool:
    return hasattr(func, "__annotations__") and func.__annotations__.get(
        "_inject", False
    )


@lru_cache(maxsize=None)
def _cached_parameters(
    func: Callable[..., Any],
) -> Tuple[Tuple[str, inspect.Parameter], ...]:
    return tuple(inspect.signature(func).parameters.items())


@lru_cache(maxsize=None)
def _cached_type_hints(func: Callable[..., Any]) -> Dict[str, Any]:
    return get_type_hints(func)


def _get_parameters(
    func: Callable[..., Any],
) -> Tuple[Tuple[str, inspect.Parameter], ...]:
    try:
        return _cached_parameters(func)
    except TypeError:
        return tuple(inspect.signature(func).parameters.items())


def _get_type_hints(func: Callable[..., Any]) -> Dict[str, Any]:
    try:
        return _cached_type_hints(func)
    except TypeError:
        return get_type_hints(func)


@lru_cache(maxsize=None)
def _cached_injected_properties(
    cls: Type,
) -> Tuple[Tuple[str, Callable[..., Any]], ...]:
    properties = []
    for name in dir(cls):
        attr = getattr(cls, name)
        if callable(attr) and is_injectable(attr):
            properties.append((name, attr))
    return tuple(properties)


@dataclass(frozen=True)
class _DependencyPlan:
    name: str
    dependency_type: Any
    dependency_key: Optional[Tuple[Union[Type, str], Optional[str]]]
    has_default: bool
    default: Any
    is_optional: bool
    inject_container: bool = False


@dataclass(frozen=True)
class _CallablePlan:
    dependencies: Tuple[_DependencyPlan, ...]


@dataclass(frozen=True)
class _ServicePlan:
    dependencies: Tuple[_DependencyPlan, ...]
    property_dependencies: Tuple[_DependencyPlan, ...]


@dataclass(frozen=True)
class _FactoryPlan:
    dependencies: Tuple[_DependencyPlan, ...]


def _normalize_dependency_type(dependency_type: Any) -> Tuple[Any, bool]:
    origin = get_origin(dependency_type)
    if origin in (Union, types.UnionType):
        args = get_args(dependency_type)
        if type(None) in args:
            non_none_args = [arg for arg in args if arg is not type(None)]
            return (non_none_args[0] if non_none_args else Any, True)
    return dependency_type, False


@lru_cache(maxsize=None)
def _cached_callable_plan(
    func: Callable[..., Any], skip_self: bool = False
) -> _CallablePlan:
    try:
        type_hints = _cached_type_hints(func)
    except Exception:
        type_hints = {}

    dependencies = []
    for name, param in _get_parameters(func):
        if skip_self and name == "self":
            continue

        has_default = param.default != inspect.Parameter.empty
        if param.annotation == inspect.Parameter.empty and name not in type_hints:
            dependencies.append(
                _DependencyPlan(
                    name=name,
                    dependency_type=inspect.Parameter.empty,
                    dependency_key=None,
                    has_default=has_default,
                    default=param.default,
                    is_optional=False,
                    inject_container=name == "container",
                )
            )
            continue

        dependency_type = type_hints.get(name, param.annotation)
        dependency_type, is_optional = _normalize_dependency_type(dependency_type)
        dependency_key = None
        if dependency_type != inspect.Parameter.empty:
            dependency_key = (dependency_type, None)
        dependencies.append(
            _DependencyPlan(
                name=name,
                dependency_type=dependency_type,
                dependency_key=dependency_key,
                has_default=has_default,
                default=param.default,
                is_optional=is_optional,
            )
        )
    return _CallablePlan(tuple(dependencies))


def _get_callable_plan(
    func: Callable[..., Any], skip_self: bool = False
) -> _CallablePlan:
    try:
        return _cached_callable_plan(func, skip_self)
    except TypeError:
        try:
            type_hints = get_type_hints(func)
        except Exception:
            type_hints = {}

        dependencies = []
        for name, param in tuple(inspect.signature(func).parameters.items()):
            if skip_self and name == "self":
                continue
            has_default = param.default != inspect.Parameter.empty
            if param.annotation == inspect.Parameter.empty and name not in type_hints:
                dependencies.append(
                    _DependencyPlan(
                        name=name,
                        dependency_type=inspect.Parameter.empty,
                        dependency_key=None,
                        has_default=has_default,
                        default=param.default,
                        is_optional=False,
                        inject_container=name == "container",
                    )
                )
                continue

            dependency_type = type_hints.get(name, param.annotation)
            dependency_type, is_optional = _normalize_dependency_type(dependency_type)
            dependency_key = None
            if dependency_type != inspect.Parameter.empty:
                dependency_key = (dependency_type, None)
            dependencies.append(
                _DependencyPlan(
                    name=name,
                    dependency_type=dependency_type,
                    dependency_key=dependency_key,
                    has_default=has_default,
                    default=param.default,
                    is_optional=is_optional,
                )
            )
        return _CallablePlan(tuple(dependencies))


@lru_cache(maxsize=None)
def _cached_property_dependencies(cls: Type) -> Tuple[_DependencyPlan, ...]:
    dependencies = []
    for name, attr in _cached_injected_properties(cast(Any, cls)):
        type_hints = _cached_type_hints(attr)
        dependency_type = type_hints.get("return")
        if dependency_type is not None and dependency_type != inspect.Parameter.empty:
            dependency_type, is_optional = _normalize_dependency_type(dependency_type)
            dependencies.append(
                _DependencyPlan(
                    name=name,
                    dependency_type=dependency_type,
                    dependency_key=(dependency_type, None),
                    has_default=False,
                    default=inspect.Parameter.empty,
                    is_optional=is_optional,
                )
            )
    return tuple(dependencies)


def _make_fast_raw_creator(
    cls: Type, dependency_creators: List[Callable[[Any], Any]]
) -> Callable[[Any], Any]:
    dependency_count = len(dependency_creators)
    if dependency_count == 0:
        return lambda scope: cls()
    if dependency_count == 1:
        dep0 = dependency_creators[0]
        return lambda scope: cls(dep0(scope))
    if dependency_count == 2:
        dep0, dep1 = dependency_creators
        return lambda scope: cls(dep0(scope), dep1(scope))
    if dependency_count == 3:
        dep0, dep1, dep2 = dependency_creators
        return lambda scope: cls(dep0(scope), dep1(scope), dep2(scope))
    if dependency_count == 4:
        dep0, dep1, dep2, dep3 = dependency_creators
        return lambda scope: cls(dep0(scope), dep1(scope), dep2(scope), dep3(scope))
    return lambda scope: cls(*(creator(scope) for creator in dependency_creators))


def _none_creator(scope: Any) -> Any:
    return None


def _make_constant_creator(value: Any) -> Callable[[Any], Any]:
    return lambda scope: value
