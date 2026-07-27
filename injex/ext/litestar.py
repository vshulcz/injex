"""Litestar integration for Injex.

Thin glue: an ASGI middleware that opens one Injex scope per request, exposes it
on ``request.state.injex``, and places the request in the scope's context.

    from litestar import Litestar
    from litestar.middleware import DefineMiddleware
    from injex.ext.litestar import InjexMiddleware

    app = Litestar(
        route_handlers=[...],
        middleware=[DefineMiddleware(InjexMiddleware, container=container)],
    )

    @get("/me")
    async def me(request: Request) -> str:
        service = await request.state.injex.aresolve(Service)
        ...

A service registered with ``container.add_context(Request)`` receives the live
``litestar.Request``. Install with ``pip install injex[litestar]``.
"""

from __future__ import annotations

from typing import Any

from litestar import Request
from litestar.types import ASGIApp, Receive, Scope, Send

from injex import Container


class InjexMiddleware:
    """Opens an Injex scope per request on ``request.state.injex`` and finalizes
    its scoped resources when the request ends."""

    def __init__(self, app: ASGIApp, container: Container) -> None:
        self.app = app
        self.container = container

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # ASGI scope["type"] is the string "http" at runtime; Litestar types it
        # as an enum, hence the ignore.
        if scope["type"] != "http":  # type: ignore[comparison-overlap]
            await self.app(scope, receive, send)
            return
        request: Request[Any, Any, Any] = Request(scope, receive, send)
        async with self.container.ascope(context={Request: request}) as injex_scope:
            scope.setdefault("state", {})["injex"] = injex_scope
            await self.app(scope, receive, send)
