"""Flask integration for Injex.

Thin glue: opens one Injex scope per request, exposes it on ``flask.g.injex``,
and places the request in the scope's context.

    from flask import Flask, g
    from injex.ext.flask import setup_injex

    app = Flask(__name__)
    setup_injex(app, container)

    @app.route("/me")
    def me():
        return g.injex.resolve(CurrentUser).user

A service registered with ``container.add_context(Request)`` receives the live
``flask.Request``. Install with ``pip install injex[flask]``.
"""

from __future__ import annotations

from flask import Flask, Request, g, request

from injex import Container


def setup_injex(app: Flask, container: Container) -> None:
    """Open an Injex scope per request on ``flask.g.injex`` and finalize its
    scoped resources when the request ends."""

    @app.before_request
    def _open_scope() -> None:
        scope = container.create_scope(
            context={Request: request._get_current_object()}  # type: ignore[attr-defined]
        )
        scope.__enter__()
        g.injex = scope

    @app.teardown_request
    def _close_scope(_exc: BaseException | None) -> None:
        scope = g.pop("injex", None)
        if scope is not None:
            scope.__exit__(None, None, None)
