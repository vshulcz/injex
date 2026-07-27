"""Sanic integration for Injex.

Thin glue: opens one Injex scope per request on ``request.ctx.injex``, with the
request in the scope's context.

    from sanic import Sanic
    from injex.ext.sanic import setup_injex

    app = Sanic("myapp")
    setup_injex(app, container)

    @app.get("/me")
    async def me(request):
        service = await request.ctx.injex.aresolve(Service)
        ...

A service registered with ``container.add_context(Request)`` receives the live
``sanic.Request``. Install with ``pip install injex[sanic]``.
"""

from __future__ import annotations

from typing import Any

from sanic import HTTPResponse, Request, Sanic

from injex import Container


def setup_injex(app: Sanic[Any, Any], container: Container) -> None:
    """Open an Injex scope per request on ``request.ctx.injex`` and finalize its
    scoped resources when the response is sent."""

    @app.on_request
    async def _open_scope(request: Request) -> None:
        scope = container.ascope(context={Request: request})
        await scope.__aenter__()
        request.ctx.injex = scope

    @app.on_response
    async def _close_scope(request: Request, response: HTTPResponse) -> None:
        scope = getattr(request.ctx, "injex", None)
        if scope is not None:
            await scope.__aexit__(None, None, None)
