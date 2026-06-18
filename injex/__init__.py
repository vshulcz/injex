"""Public package facade for Injex."""

from .container import AsyncScope, Container, Scope
from .errors import (
    AsyncResolutionRequiredException,
    ContainerValidationException,
    CyclicDependencyException,
    DIException,
    InvalidLifestyleException,
    MissingTypeAnnotationException,
    PropertyInjectionException,
    ServiceNotRegisteredException,
    ValidationError,
    _describe_service as _describe_service,
)
from .planning import (
    _cached_callable_plan as _cached_callable_plan,
    _cached_injected_properties as _cached_injected_properties,
    _cached_type_hints as _cached_type_hints,
    _DependencyPlan as _DependencyPlan,
    _get_callable_plan as _get_callable_plan,
    _get_type_hints as _get_type_hints,
    _make_fast_raw_creator as _make_fast_raw_creator,
    inject,
    is_injectable as is_injectable,
)
from .registry import (
    LifeStyle,
    OverrideContext as OverrideContext,
    Registration as Registration,
    RegistrationType as RegistrationType,
)

__all__ = [
    "AsyncResolutionRequiredException",
    "AsyncScope",
    "Container",
    "ContainerValidationException",
    "CyclicDependencyException",
    "DIException",
    "InvalidLifestyleException",
    "LifeStyle",
    "MissingTypeAnnotationException",
    "PropertyInjectionException",
    "Scope",
    "ServiceNotRegisteredException",
    "ValidationError",
    "inject",
]
