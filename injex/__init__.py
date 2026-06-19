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
)
from .errors import (
    _describe_service as _describe_service,
)
from .planning import (
    _cached_callable_plan as _cached_callable_plan,
)
from .planning import (
    _cached_injected_properties as _cached_injected_properties,
)
from .planning import (
    _cached_type_hints as _cached_type_hints,
)
from .planning import (
    _DependencyPlan as _DependencyPlan,
)
from .planning import (
    _get_callable_plan as _get_callable_plan,
)
from .planning import (
    _get_type_hints as _get_type_hints,
)
from .planning import (
    _make_fast_raw_creator as _make_fast_raw_creator,
)
from .planning import (
    inject,
)
from .planning import (
    is_injectable as is_injectable,
)
from .registry import (
    LifeStyle,
)
from .registry import (
    OverrideContext as OverrideContext,
)
from .registry import (
    Registration as Registration,
)
from .registry import (
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
