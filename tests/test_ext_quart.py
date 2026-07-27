"""Quart integration: per-request scope on quart.g.injex, the request in the
scope context, and scoped resources finalized when the request ends."""

import asyncio

import pytest

pytest.importorskip("quart")

from collections.abc import AsyncIterator

from quart import Quart, Request, g

from injex import Container
from injex.ext.quart import setup_injex


def _app(container: Container) -> Quart:
    app = Quart(__name__)
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
    async def me() -> str:
        user: CurrentUser = await g.injex.aresolve(CurrentUser)
        return user.user

    async def go() -> tuple[str, str]:
        client = app.test_client()
        r1 = await client.get("/me", headers={"X-User": "ada"})
        r2 = await client.get("/me", headers={"X-User": "bob"})
        return (await r1.get_data()).decode(), (await r2.get_data()).decode()

    assert asyncio.run(go()) == ("ada", "bob")  # context is per request


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
    async def view() -> str:
        await g.injex.aresolve(Session)
        events.append("view")
        return "ok"

    async def go() -> None:
        await app.test_client().get("/")

    asyncio.run(go())
    assert events == ["open", "view", "close"]
