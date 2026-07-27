"""aiohttp integration: per-request scope on request["injex"], the request in
the scope context, and scoped resources finalized when the request ends."""

import asyncio

import pytest

pytest.importorskip("aiohttp")

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from injex import Container
from injex.ext.aiohttp import injex_middleware


async def _fetch(container: Container, routes: list, path: str, **headers) -> str:
    app = web.Application(middlewares=[injex_middleware(container)])
    app.add_routes(routes)
    async with TestClient(TestServer(app)) as client:
        response = await client.get(path, headers=headers)
        return await response.text()


def test_middleware_resolves_and_injects_the_request():
    class CurrentUser:
        def __init__(self, request: web.Request) -> None:
            self.user = request.headers.get("X-User", "anon")

    container = Container()
    container.add_context(web.Request)
    container.add_transient(CurrentUser)

    async def me(request: web.Request) -> web.Response:
        user = await request["injex"].aresolve(CurrentUser)
        return web.Response(text=user.user)

    async def go() -> tuple[str, str]:
        with_header = await _fetch(
            container, [web.get("/me", me)], "/me", **{"X-User": "ada"}
        )
        without = await _fetch(container, [web.get("/me", me)], "/me")
        return with_header, without

    assert asyncio.run(go()) == ("ada", "anon")


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

    async def view(request: web.Request) -> web.Response:
        await request["injex"].aresolve(Session)
        events.append("view")
        return web.Response(text="ok")

    asyncio.run(_fetch(container, [web.get("/", view)], "/"))
    assert events == ["open", "view", "close"]
