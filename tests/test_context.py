"""Context data: values supplied per-scope by the caller (e.g. the request) and
injected into the graph. add_context() declares them; validate() treats them as
satisfied; resolving reads them from the scope's context."""

import asyncio

import pytest

from injex import Container, ContextValueMissingException


class Request:
    def __init__(self, user: str) -> None:
        self.user = user


class Handler:
    def __init__(self, request: Request) -> None:
        self.request = request


class Service:  # transitive: depends on Handler which depends on the context
    def __init__(self, handler: Handler) -> None:
        self.handler = handler


def _container() -> Container:
    c = Container()
    c.add_context(Request)
    c.add_transient(Handler)
    c.add_transient(Service)
    return c


def test_context_dependency_counts_as_satisfied_in_validate():
    assert _container().validate() == []


def test_resolves_context_value_into_the_graph():
    c = _container()
    req = Request("ada")
    with c.create_scope(context={Request: req}) as scope:
        assert scope.resolve(Handler).request is req
        # transitive: Service -> Handler -> Request
        assert scope.resolve(Service).handler.request is req
        # resolving the context type directly returns the value
        assert scope.resolve(Request) is req


def test_each_scope_sees_its_own_context_value():
    c = _container()
    with c.create_scope(context={Request: Request("a")}) as scope:
        assert scope.resolve(Handler).request.user == "a"
    with c.create_scope(context={Request: Request("b")}) as scope:
        assert scope.resolve(Handler).request.user == "b"


def test_missing_context_value_raises_clearly():
    c = _container()
    with (
        c.create_scope() as scope,  # no context provided
        pytest.raises(ContextValueMissingException) as excinfo,
    ):
        scope.resolve(Handler)
    assert "Request" in str(excinfo.value)


def test_top_level_resolve_without_a_scope_raises():
    c = _container()
    with pytest.raises(ContextValueMissingException):
        c.resolve(Handler)


def test_context_works_through_the_async_path():
    async def go() -> tuple[str, str]:
        c = _container()
        async with c.ascope(context={Request: Request("x")}) as scope:
            first = (await scope.aresolve(Service)).handler.request.user
        async with c.ascope(context={Request: Request("y")}) as scope:
            second = (await scope.aresolve(Handler)).request.user
        return first, second

    assert asyncio.run(go()) == ("x", "y")


def test_missing_context_raises_on_the_async_path():
    async def go() -> None:
        c = _container()
        async with c.ascope() as scope:
            await scope.aresolve(Handler)

    with pytest.raises(ContextValueMissingException):
        asyncio.run(go())


def test_context_coexists_with_scoped_and_singleton_services():
    class Config:
        pass

    class Db:  # scoped
        def __init__(self, config: Config) -> None:
            self.config = config

    class Repo:
        def __init__(self, db: Db, request: Request) -> None:
            self.db = db
            self.request = request

    c = Container()
    c.add_singleton(Config)
    c.add_scoped(Db)
    c.add_context(Request)
    c.add_transient(Repo)
    assert c.validate() == []

    req = Request("tenant-1")
    with c.create_scope(context={Request: req}) as scope:
        a = scope.resolve(Repo)
        b = scope.resolve(Repo)
        assert a.request is req
        assert a.db is b.db  # scoped Db shared within the scope
