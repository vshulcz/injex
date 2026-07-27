"""Flask integration: per-request scope on flask.g.injex, the request in the
scope context, and scoped resources finalized when the request ends."""

import pytest

pytest.importorskip("flask")

from collections.abc import Iterator

from flask import Flask, Request, g

from injex import Container
from injex.ext.flask import setup_injex


def _app(container: Container) -> Flask:
    app = Flask(__name__)
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

    @app.route("/me")
    def me() -> str:
        return g.injex.resolve(CurrentUser).user

    client = app.test_client()
    assert client.get("/me", headers={"X-User": "ada"}).text == "ada"
    assert client.get("/me").text == "anon"  # per request


def test_scoped_resource_finalized_after_response():
    events: list[str] = []

    class Session: ...

    def open_session() -> Iterator[Session]:
        events.append("open")
        try:
            yield Session()
        finally:
            events.append("close")

    container = Container()
    container.add_scoped_factory(Session, open_session)

    app = _app(container)

    @app.route("/")
    def view() -> str:
        g.injex.resolve(Session)
        events.append("view")
        return "ok"

    app.test_client().get("/")
    assert events == ["open", "view", "close"]
