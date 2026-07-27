"""aiohttp integration for Injex.

Thin glue: a middleware that opens one Injex scope per request, exposes it on
``request["injex"]``, and places the request in the scope's context.

    from aiohttp import web
    from injex.ext.aiohttp import injex_middleware

    app = web.Application(middlewares=[injex_middleware(container)])

    async def handler(request):
        service = await request["injex"].aresolve(Service)
        ...

A service registered with ``container.add_context(web.Request)`` receives the
live ``aiohttp.web.Request``. Install with ``pip install injex[aiohttp]``.
"""

from __future__ import annotations

from aiohttp import web
from aiohttp.typedefs import Handler, Middleware

from injex import Container


def injex_middleware(container: Container) -> Middleware:
    """Build an aiohttp middleware that opens an Injex scope per request on
    ``request["injex"]`` and finalizes its scoped resources when the request ends."""

    @web.middleware
    async def middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
        async with container.ascope(context={web.Request: request}) as scope:
            request["injex"] = scope
            return await handler(request)

    return middleware
