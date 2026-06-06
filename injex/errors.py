from dataclasses import dataclass
from typing import List, Optional, Type, Union


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
            f"Invalid lifestyle '{lifestyle}'. Valid options are 'transient', 'singleton', or 'scoped'."
        )


@dataclass(frozen=True)
class ValidationError:
    service: Union[Type, str]
    name: Optional[str]
    message: str

    def __str__(self) -> str:
        service = _describe_service(self.service)
        if self.name is not None:
            service += f" named '{self.name}'"
        return f"{service}: {self.message}"


class ContainerValidationException(DIException):
    def __init__(self, errors: List[ValidationError]):
        self.errors = errors
        details = "\n".join(f"- {error}" for error in errors)
        super().__init__(
            f"Container validation failed with {len(errors)} error(s):\n{details}"
        )


def _describe_service(service: Union[Type, str]) -> str:
    if isinstance(service, str):
        return service
    return getattr(service, "__name__", str(service))
