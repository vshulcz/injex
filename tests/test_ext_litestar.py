"""Litestar integration: per-request scope on request.state.injex, the request
in the scope context, and scoped resources finalized after the response."""

import pytest

pytest.importorskip("litestar")

from litestar import Litestar, Request, get
from litestar.middleware import DefineMiddleware
from litestar.testing import TestClient

from injex import Container
from injex.ext.litestar import InjexMiddleware


def _client(container: Container, handlers: list) -> TestClient:
    app = Litestar(
        route_handlers=handlers,
        middleware=[DefineMiddleware(InjexMiddleware, container=container)],
    )
    return TestClient(app=app)


def test_middleware_resolves_and_injects_the_request():
    class CurrentUser:
        def __init__(self, request: Request) -> None:
            self.user = request.headers.get("x-user", "anon")

    container = Container()
    container.add_context(Request)
    container.add_transient(CurrentUser)

    @get("/me")
    async def me(request: Request) -> str:
        return (await request.state.injex.aresolve(CurrentUser)).user

    with _client(container, [me]) as client:
        assert client.get("/me", headers={"x-user": "ada"}).text == "ada"
        assert client.get("/me").text == "anon"


def test_scoped_resource_finalized_after_response():
    events: list[str] = []

    class Session: ...

    async def open_session():
        events.append("open")
        try:
            yield Session()
        finally:
            events.append("close")

    container = Container()
    container.add_scoped_factory(Session, open_session)

    @get("/")
    async def view(request: Request) -> str:
        await request.state.injex.aresolve(Session)
        events.append("view")
        return "ok"

    with _client(container, [view]) as client:
        client.get("/")
    assert events == ["open", "view", "close"]
