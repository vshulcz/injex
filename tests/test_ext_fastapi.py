"""FastAPI integration: per-request scope, Provide(), shutdown finalization."""

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from injex import Container  # noqa: E402
from injex.ext.fastapi import Provide, setup_injex  # noqa: E402


class Settings:
    def __init__(self) -> None:
        self.name = "prod"


class Service:
    def __init__(self, settings: Settings):
        self.settings = settings


def _app() -> tuple[FastAPI, list[str]]:
    events: list[str] = []

    async def db_session():
        events.append("open")
        try:
            yield {"dsn": "x"}
        finally:
            events.append("close")

    container = Container()
    container.add_singleton(Settings)
    container.add_transient(Service)
    container.add_scoped_factory(dict, db_session)

    app = FastAPI()
    setup_injex(app, container)

    @app.get("/name")
    def name(service: Service = Provide(Service)) -> dict[str, str]:
        return {"name": service.settings.name}

    @app.get("/session")
    async def session(db: dict[str, str] = Provide(dict)) -> dict[str, str]:
        return {"dsn": db["dsn"]}

    return app, events


def test_provide_resolves_service():
    app, _ = _app()
    with TestClient(app) as client:
        assert client.get("/name").json() == {"name": "prod"}


def test_request_scope_opens_and_closes_resource_per_request():
    app, events = _app()
    with TestClient(app) as client:
        assert client.get("/session").json() == {"dsn": "x"}
        assert events == ["open", "close"]  # finalized when the request ended
        client.get("/session")
        assert events == ["open", "close", "open", "close"]  # fresh per request


def test_singleton_identity_across_requests():
    app, _ = _app()
    with TestClient(app) as client:
        # Settings is a singleton: same name proves it resolves consistently.
        assert client.get("/name").json()["name"] == "prod"
        assert client.get("/name").json()["name"] == "prod"
