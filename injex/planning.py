import inspect
import types
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import (
    Annotated,
    Any,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)


@dataclass(frozen=True)
class Named:
    """Marker for an `Annotated` dependency that selects a named registration.

    ``def __init__(self, db: Annotated[Database, Named("primary")]): ...``
    injects the registration made with ``name="primary"``.
    """

    name: str


_INJECT_FLAG = "__injex_inject__"


def inject(func: Callable[..., Any]) -> Callable[..., Any]:
    """Mark a method for property injection (its return type is resolved and set
    as an attribute). Kept off ``__annotations__`` so it never leaks into
    ``get_type_hints``."""
    setattr(func, _INJECT_FLAG, True)
    return func


def is_injectable(func: Callable[..., Any]) -> bool:
    return getattr(func, _INJECT_FLAG, False)


@cache
def _cached_parameters(
    func: Callable[..., Any],
) -> tuple[tuple[str, inspect.Parameter], ...]:
    return tuple(inspect.signature(func).parameters.items())


@cache
def _cached_type_hints(func: Callable[..., Any]) -> dict[str, Any]:
    # include_extras keeps Annotated metadata so Named(...) markers survive.
    return get_type_hints(func, include_extras=True)


def _get_parameters(
    func: Callable[..., Any],
) -> tuple[tuple[str, inspect.Parameter], ...]:
    try:
        return _cached_parameters(func)
    except TypeError:
        return tuple(inspect.signature(func).parameters.items())


def _get_type_hints(func: Callable[..., Any]) -> dict[str, Any]:
    try:
        return _cached_type_hints(func)
    except TypeError:
        return get_type_hints(func)


@cache
def _cached_injected_properties(
    cls: type,
) -> tuple[tuple[str, Callable[..., Any]], ...]:
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
    dependency_key: tuple[type | str, str | None] | None
    has_default: bool
    default: Any
    is_optional: bool
    inject_container: bool = False


@dataclass(frozen=True)
class _CallablePlan:
    dependencies: tuple[_DependencyPlan, ...]


@dataclass(frozen=True)
class _ServicePlan:
    dependencies: tuple[_DependencyPlan, ...]
    property_dependencies: tuple[_DependencyPlan, ...]


@dataclass(frozen=True)
class _FactoryPlan:
    dependencies: tuple[_DependencyPlan, ...]


def _unwrap_annotated(dependency_type: Any) -> tuple[Any, str | None]:
    """Strip an ``Annotated`` wrapper, returning the type and any ``Named``."""
    if get_origin(dependency_type) is Annotated:
        args = get_args(dependency_type)
        name = next((m.name for m in args[1:] if isinstance(m, Named)), None)
        return args[0], name
    return dependency_type, None


def _normalize_dependency_type(dependency_type: Any) -> tuple[Any, bool, str | None]:
    dependency_type, name = _unwrap_annotated(dependency_type)
    origin = get_origin(dependency_type)
    if origin in (Union, types.UnionType):
        args = get_args(dependency_type)
        if type(None) in args:
            non_none_args = [arg for arg in args if arg is not type(None)]
            inner = non_none_args[0] if non_none_args else Any
            inner, inner_name = _unwrap_annotated(inner)
            return inner, True, (name or inner_name)
    return dependency_type, False, name


@cache
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
        dependency_type, is_optional, dep_name = _normalize_dependency_type(
            dependency_type
        )
        dependency_key = None
        if dependency_type != inspect.Parameter.empty:
            dependency_key = (dependency_type, dep_name)
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
            dependency_type, is_optional, dep_name = _normalize_dependency_type(
                dependency_type
            )
            dependency_key = None
            if dependency_type != inspect.Parameter.empty:
                dependency_key = (dependency_type, dep_name)
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


@cache
def _cached_property_dependencies(cls: type) -> tuple[_DependencyPlan, ...]:
    dependencies = []
    for name, attr in _cached_injected_properties(cast(Any, cls)):
        type_hints = _cached_type_hints(attr)
        dependency_type = type_hints.get("return")
        if dependency_type is not None and dependency_type != inspect.Parameter.empty:
            dependency_type, is_optional, dep_name = _normalize_dependency_type(
                dependency_type
            )
            dependencies.append(
                _DependencyPlan(
                    name=name,
                    dependency_type=dependency_type,
                    dependency_key=(dependency_type, dep_name),
                    has_default=False,
                    default=inspect.Parameter.empty,
                    is_optional=is_optional,
                )
            )
    return tuple(dependencies)


def _make_fast_raw_creator(
    cls: type, dependency_creators: list[Callable[[Any], Any]]
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
