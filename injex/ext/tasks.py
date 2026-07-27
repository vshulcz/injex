"""Inject services into task and handler functions in any framework — Celery,
arq, RQ, dramatiq, aiogram, and so on. Each call opens one Injex scope, so scoped
resources (a DB session, a unit of work) get a per-task lifetime with teardown,
and the function's ``Inject()``-marked parameters are resolved from that scope.

No dependency on any of those frameworks: the decorator only rewrites the wrapped
function's signature (hiding the injected parameters), which is what the task
runners and routers read.

    from injex.ext.tasks import inject, ainject
    from injex.ext.cli import Inject

    @app.task                      # Celery
    @inject(container)
    def process(order_id: int, orders: OrderService = Inject()):
        orders.process(order_id)

    @router.message()              # aiogram
    @ainject(container)
    async def handle(message, users: UserService = Inject()):
        await users.register(message.from_user.id)
"""

import functools
import inspect
from collections.abc import Callable
from typing import Any, TypeVar

from injex import Container
from injex.ext.cli import _INJECT

T = TypeVar("T")


def _split_parameters(
    func: Callable[..., Any],
) -> tuple[inspect.Signature, list[inspect.Parameter], list[inspect.Parameter]]:
    signature = inspect.signature(func)
    injected = [p for p in signature.parameters.values() if p.default is _INJECT]
    visible = [p for p in signature.parameters.values() if p.default is not _INJECT]
    for param in injected:
        if param.annotation is inspect.Parameter.empty:
            raise TypeError(
                f"Parameter '{param.name}' of {func.__name__}() is marked Inject() "
                "but has no type annotation; add one so injex knows what to resolve."
            )
    return signature, injected, visible


def _provided_from_call(
    visible: list[inspect.Parameter], args: tuple[Any, ...], kwargs: dict[str, Any]
) -> dict[str, Any]:
    provided = dict(kwargs)
    for param, value in zip(visible, args, strict=False):
        provided[param.name] = value
    return provided


def inject(container: Container) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Open an Injex scope per call and resolve the ``Inject()``-marked
    parameters from it. Scoped resources are finalized when the call returns."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        signature, injected, visible = _split_parameters(func)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            provided = _provided_from_call(visible, args, kwargs)
            with container.create_scope() as scope:
                for param in injected:
                    provided[param.name] = scope.resolve(param.annotation)
                return func(**provided)

        wrapper.__signature__ = signature.replace(parameters=visible)  # type: ignore[attr-defined]
        return wrapper

    return decorator


def ainject(container: Container) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Async counterpart of :func:`inject`: opens an async scope per call and
    awaits async factories/resources. The wrapped function may be sync or async."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        signature, injected, visible = _split_parameters(func)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            provided = _provided_from_call(visible, args, kwargs)
            async with container.ascope() as scope:
                for param in injected:
                    provided[param.name] = await scope.aresolve(param.annotation)
                result = func(**provided)
                if inspect.isawaitable(result):
                    result = await result
                return result

        wrapper.__signature__ = signature.replace(parameters=visible)  # type: ignore[attr-defined]
        return wrapper

    return decorator
