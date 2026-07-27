"""Starlette integration for Injex.

Thin glue: a middleware that opens one Injex scope per request, exposes it on
``request.state.injex``, and places the request in the scope's context.

    from starlette.applications import Starlette
    from injex.ext.starlette import InjexMiddleware

    app = Starlette(routes=[...])
    app.add_middleware(InjexMiddleware, container=container)

    async def handler(request):
        service = await request.state.injex.aresolve(Service)
        ...

A service registered with ``container.add_context(Request)`` receives the live
``starlette.requests.Request``. Install with ``pip install injex[starlette]``.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from injex import Container


class InjexMiddleware(BaseHTTPMiddleware):
    """Opens an Injex scope per request on ``request.state.injex`` and finalizes
    its scoped resources when the response is returned."""

    def __init__(self, app: ASGIApp, container: Container) -> None:
        super().__init__(app)
        self.container = container

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        async with self.container.ascope(context={Request: request}) as scope:
            request.state.injex = scope
            return await call_next(request)
