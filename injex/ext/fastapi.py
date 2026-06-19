"""FastAPI integration for Injex.

Thin glue, not a new container: it opens one Injex scope per request and lets
route handlers receive container services through FastAPI's own ``Depends``.

    from fastapi import FastAPI
    from injex import Container
    from injex.ext.fastapi import Provide, setup_injex

    container = build_container()
    app = FastAPI()
    setup_injex(app, container)

    @app.post("/users")
    async def create(use_case: RegisterUser = Provide(RegisterUser)):
        return use_case.execute(...)

Install with ``pip install injex[fastapi]``.
"""

from collections.abc import AsyncIterator
from typing import Any, TypeVar, cast

from fastapi import Depends, FastAPI, Request

from injex import AsyncScope, Container

T = TypeVar("T")


def setup_injex(app: FastAPI, container: Container) -> Container:
    """Attach ``container`` to ``app`` and finalize its resources on shutdown.

    Stores the container on ``app.state`` so per-request scopes can find it, and
    registers a shutdown handler that closes singleton async and sync resources.
    """
    app.state.injex_container = container

    async def _shutdown() -> None:
        await container.aclose()
        container.close()

    # Register on the router's shutdown hook (works across Starlette versions).
    cast(Any, app).router.add_event_handler("shutdown", _shutdown)
    return container


async def _request_scope(request: Request) -> AsyncIterator[AsyncScope]:
    """One Injex scope per request. FastAPI caches this dependency within a
    request, so every ``Provide`` in the same request shares the scope; its
    resources are finalized when the request ends."""
    container: Container = request.app.state.injex_container
    async with container.ascope() as scope:
        yield scope


def Provide(interface: type[T], name: str | None = None) -> Any:
    """A FastAPI dependency that resolves ``interface`` from the request scope.

    Use it as a parameter default::

        async def handler(svc: Service = Provide(Service)): ...
    """

    async def _dependency(scope: AsyncScope = Depends(_request_scope)) -> T:
        return cast(T, await scope.aresolve(interface, name))

    return Depends(_dependency)
