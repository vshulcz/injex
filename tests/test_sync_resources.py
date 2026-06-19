"""Sync resources: generator factories with teardown around a scope / container."""

import pytest

from injex import Container


class Settings:
    pass


def test_scoped_resource_finalized_on_scope_exit():
    events = []

    def session():
        events.append("open")
        try:
            yield "SESSION"
        finally:
            events.append("close")

    c = Container()
    c.add_scoped_factory(str, session)

    with c.create_scope() as scope:
        a = scope.resolve(str)
        b = scope.resolve(str)
        assert a == b == "SESSION"  # one resource per scope
        assert events == ["open"]
    assert events == ["open", "close"]  # finalized on scope exit


def test_transient_resource_finalized_on_scope_exit():
    events = []

    def handle():
        events.append("open")
        try:
            yield object()
        finally:
            events.append("close")

    c = Container()
    c.add_transient_factory(object, handle)

    with c.create_scope() as scope:
        a = scope.resolve(object)
        b = scope.resolve(object)
        assert a is not b  # fresh per resolve
        assert events == ["open", "open"]
    assert events == ["open", "open", "close", "close"]  # both closed, LIFO


def test_singleton_resource_finalized_on_close():
    events = []

    def pool():
        events.append("open")
        try:
            yield "POOL"
        finally:
            events.append("close")

    c = Container()
    c.add_singleton_factory(str, pool)
    assert c.resolve(str) == "POOL"
    assert c.resolve(str) == "POOL"
    assert events == ["open"]  # built once, survives between resolves
    c.close()
    assert events == ["open", "close"]


def test_container_context_manager_closes_singleton_resources():
    events = []

    def res():
        events.append("open")
        try:
            yield 1
        finally:
            events.append("close")

    with Container() as c:
        c.add_singleton_factory(int, res)
        c.resolve(int)
    assert events == ["open", "close"]


def test_singleton_resource_reopens_after_close():
    events = []

    def res():
        events.append("open")
        try:
            yield object()
        finally:
            events.append("close")

    c = Container()
    c.add_singleton_factory(object, res)
    a = c.resolve(object)
    c.close()
    b = c.resolve(object)  # evicted on close -> rebuilt, not the closed instance
    assert a is not b
    assert events == ["open", "close", "open"]


def test_resource_injected_into_service_within_scope():
    events = []

    def session(settings: Settings):
        events.append("open")
        try:
            yield {"dsn": "x"}
        finally:
            events.append("close")

    class Repo:
        def __init__(self, session: dict):
            self.session = session

    c = Container()
    c.add_instance(Settings, Settings())
    c.add_scoped_factory(dict, session)
    c.add_transient(Repo)

    with c.create_scope() as scope:
        repo = scope.resolve(Repo)
        assert repo.session == {"dsn": "x"}
        assert events == ["open"]
    assert events == ["open", "close"]


def test_container_resolve_of_scoped_resource_is_guarded():
    def session():
        yield "x"

    c = Container()
    c.add_scoped_factory(str, session)
    with pytest.raises(ValueError, match="create_scope"):
        c.resolve(str)
