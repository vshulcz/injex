"""Starlette integration: per-request scope on request.state.injex, the request
in the scope context, and scoped resources finalized after the response."""

import pytest

pytest.importorskip("starlette")

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from injex import Container
from injex.ext.starlette import InjexMiddleware


def _client(container: Container, routes: list[Route]) -> TestClient:
    app = Starlette(routes=routes)
    app.add_middleware(InjexMiddleware, container=container)
    return TestClient(app)


def test_middleware_resolves_and_injects_the_request():
    class CurrentUser:
        def __init__(self, request: Request) -> None:
            self.user = request.headers.get("x-user", "anon")

    container = Container()
    container.add_context(Request)
    container.add_transient(CurrentUser)

    async def me(request: Request) -> PlainTextResponse:
        user = await request.state.injex.aresolve(CurrentUser)
        return PlainTextResponse(user.user)

    with _client(container, [Route("/me", me)]) as client:
        assert client.get("/me", headers={"x-user": "ada"}).text == "ada"
        assert client.get("/me").text == "anon"  # per request


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

    async def view(request: Request) -> PlainTextResponse:
        await request.state.injex.aresolve(Session)
        events.append("view")
        return PlainTextResponse("ok")

    with _client(container, [Route("/", view)]) as client:
        client.get("/")
    assert events == ["open", "view", "close"]
