"""Inject services into CLI command functions (Typer, Click, argparse, …).

Mark the injected parameters with ``Inject()`` and wrap the command with
``wire(container)``. The CLI framework only sees the remaining parameters, so it
builds options/arguments for those while the services come from the container.

    import typer
    from injex.ext.cli import Inject, wire

    app = typer.Typer()

    @app.command()
    @wire(container)
    def greet(name: str, greeter: Greeter = Inject()):
        print(greeter.greet(name))

Framework-agnostic: it only rewrites the wrapped function's signature, which is
what Typer, Click, and the standard library all read.
"""

import functools
import inspect
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from injex import Container

T = TypeVar("T")


class _InjectMarker:
    __slots__ = ()


_INJECT = _InjectMarker()


def Inject() -> Any:
    """Default marker for a parameter that should be injected, not asked of the
    CLI. See the module docstring."""
    return _INJECT


def wire(container: "Container") -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that injects the ``Inject()``-marked parameters of a command
    from ``container`` and hides them from the CLI framework's view."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        signature = inspect.signature(func)
        visible = [
            param
            for param in signature.parameters.values()
            if param.default is not _INJECT
        ]

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            provided = dict(kwargs)
            for param, value in zip(visible, args, strict=False):
                provided[param.name] = value
            return container.call(func, **provided)

        wrapper.__signature__ = signature.replace(parameters=visible)  # type: ignore[attr-defined]
        return wrapper

    return decorator
