"""Quart integration for Injex.

Thin glue: opens one Injex scope per request on ``quart.g.injex``, with the
request in the scope's context.

    from quart import Quart, g
    from injex.ext.quart import setup_injex

    app = Quart(__name__)
    setup_injex(app, container)

    @app.get("/me")
    async def me():
        service = await g.injex.aresolve(Service)
        ...

A service registered with ``container.add_context(Request)`` receives the live
``quart.Request``. Install with ``pip install injex[quart]``.
"""

from __future__ import annotations

from quart import Quart, Request, g, request

from injex import Container


def setup_injex(app: Quart, container: Container) -> None:
    """Open an Injex scope per request on ``quart.g.injex`` and finalize its
    scoped resources when the request ends."""

    @app.before_request
    async def _open_scope() -> None:
        scope = container.ascope(
            context={Request: request._get_current_object()}  # type: ignore[attr-defined]
        )
        await scope.__aenter__()
        g.injex = scope

    @app.teardown_request
    async def _close_scope(_exc: BaseException | None) -> None:
        scope = g.pop("injex", None)
        if scope is not None:
            await scope.__aexit__(None, None, None)
