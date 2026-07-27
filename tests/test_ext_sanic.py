"""Sanic integration: per-request scope on request.ctx.injex, the request in the
scope context, and scoped resources finalized when the response is sent."""

from collections.abc import AsyncIterator
from typing import Any

import pytest

pytest.importorskip("sanic")
pytest.importorskip("sanic_testing")

from sanic import Request, Sanic, json, text
from sanic_testing import TestManager

from injex import Container
from injex.ext.sanic import setup_injex

_counter = [0]


def _app(container: Container) -> Sanic[Any, Any]:
    _counter[0] += 1
    app = Sanic(f"injextest{_counter[0]}")
    TestManager(app)
    setup_injex(app, container)
    return app


def test_middleware_resolves_and_injects_the_request():
    class CurrentUser:
        def __init__(self, request: Request) -> None:
            self.user = request.headers.get("X-User", "anon")

    container = Container()
    container.add_context(Request)
    container.add_transient(CurrentUser)

    app = _app(container)

    @app.get("/me")
    async def me(request: Request):
        user = await request.ctx.injex.aresolve(CurrentUser)
        return json({"user": user.user})

    _, r1 = app.test_client.get("/me", headers={"X-User": "ada"})
    _, r2 = app.test_client.get("/me", headers={"X-User": "bob"})
    assert r1.json["user"] == "ada"
    assert r2.json["user"] == "bob"  # context is per request


def test_scoped_resource_finalized_after_response():
    events: list[str] = []

    class Session: ...

    async def open_session() -> AsyncIterator[Session]:
        events.append("open")
        try:
            yield Session()
        finally:
            events.append("close")

    container = Container()
    container.add_scoped_factory(Session, open_session)

    app = _app(container)

    @app.get("/")
    async def view(request: Request):
        await request.ctx.injex.aresolve(Session)
        events.append("view")
        return text("ok")

    app.test_client.get("/")
    assert events == ["open", "view", "close"]
