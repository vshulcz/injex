from dataclasses import dataclass
from typing import Any


class DIException(Exception):
    """Base exception class for dependency injection errors."""


class ServiceNotRegisteredException(DIException):
    def __init__(
        self, interface_description: str, required_by: str | None = None
    ) -> None:
        message = f"Service for interface '{interface_description}' is not registered."
        if required_by is not None:
            message += f" It is required by {required_by}."
        super().__init__(message)


class CyclicDependencyException(DIException):
    def __init__(self, cls: type | str):
        super().__init__(f"Cyclic dependency detected: {_describe_service(cls)}.")


class MissingTypeAnnotationException(DIException):
    # `owner` is the class or function that declared the parameter.
    def __init__(self, param_name: str, owner: Any):
        super().__init__(
            f"Missing type annotation for parameter '{param_name}' "
            f"in '{getattr(owner, '__name__', owner)}'."
        )


class InvalidLifestyleException(DIException):
    def __init__(self, lifestyle: str):
        super().__init__(
            f"Invalid lifestyle '{lifestyle}'. "
            "Valid options are 'transient', 'singleton', or 'scoped'."
        )


class AsyncResolutionRequiredException(DIException):
    def __init__(self, factory: object):
        name = getattr(factory, "__name__", repr(factory))
        super().__init__(
            f"'{name}' is an async factory or resource and cannot be resolved "
            "synchronously. Use 'await container.aresolve(...)' or "
            "'async with container.ascope() as scope: await scope.aresolve(...)'."
        )


class PropertyInjectionException(DIException):
    def __init__(self, cls: type, name: str):
        super().__init__(
            f"Cannot inject property '{name}' on '{getattr(cls, '__name__', cls)}': "
            "the type uses __slots__ or is a frozen dataclass, so attributes "
            "cannot be set after construction. Use constructor injection for "
            "this dependency instead."
        )


@dataclass(frozen=True)
class ValidationError:
    service: type | str
    name: str | None
    message: str

    def __str__(self) -> str:
        service = _describe_service(self.service)
        if self.name is not None:
            service += f" named '{self.name}'"
        return f"{service}: {self.message}"


class ContainerValidationException(DIException):
    def __init__(self, errors: list[ValidationError]):
        self.errors = errors
        details = "\n".join(f"- {error}" for error in errors)
        super().__init__(
            f"Container validation failed with {len(errors)} error(s):\n{details}"
        )


def _describe_service(service: type | str) -> str:
    if isinstance(service, str):
        return service
    return getattr(service, "__name__", str(service))
