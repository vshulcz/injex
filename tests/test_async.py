"""Async resolution: async factories, async-generator resources with teardown,
scope/singleton lifecycle, and that the sync path rejects async work.

Tests drive coroutines with ``asyncio.run`` so no pytest plugin is required.
"""

import asyncio

import pytest

from injex import (
    AsyncResolutionRequiredException,
    Container,
    CyclicDependencyException,
)


class Settings:
    pass


class Db:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.closed = False


class Service:
    def __init__(self, db: Db, settings: Settings):
        self.db = db
        self.settings = settings


# Module-level so the forward-ref cycle resolves via get_type_hints.
class CycleA:
    def __init__(self, b: "CycleB"):
        self.b = b


class CycleB:
    def __init__(self, a: "CycleA"):
        self.a = a


def test_async_factory_is_awaited():
    async def make_settings() -> Settings:
        await asyncio.sleep(0)
        return Settings()

    async def main():
        c = Container()
        c.add_singleton_factory(Settings, make_settings)
        s1 = await c.aresolve(Settings)
        s2 = await c.aresolve(Settings)
        assert isinstance(s1, Settings)
        assert s1 is s2  # singleton

    asyncio.run(main())


def test_async_resource_finalized_on_scope_exit():
    events = []

    async def db_session():
        db = Db("postgres://")
        events.append("open")
        try:
            yield db
        finally:
            db.closed = True
            events.append("close")

    async def main():
        c = Container()
        c.add_scoped_factory(Db, db_session)
        async with c.ascope() as scope:
            d1 = await scope.aresolve(Db)
            d2 = await scope.aresolve(Db)
            assert d1 is d2  # scoped: reused within the scope
            assert events == ["open"]
            assert d1.closed is False
        assert events == ["open", "close"]  # finalized on scope exit
        assert d1.closed is True

    asyncio.run(main())


def test_new_scope_gets_a_fresh_scoped_resource():
    async def db_session():
        yield Db("x")

    async def main():
        c = Container()
        c.add_scoped_factory(Db, db_session)
        async with c.ascope() as s1:
            a = await s1.aresolve(Db)
        async with c.ascope() as s2:
            b = await s2.aresolve(Db)
        assert a is not b

    asyncio.run(main())


def test_singleton_async_resource_finalized_on_aclose():
    events = []

    async def pool():
        events.append("open")
        try:
            yield "POOL"
        finally:
            events.append("close")

    async def main():
        c = Container()
        c.add_singleton_factory(str, pool)
        p1 = await c.aresolve(str)
        p2 = await c.aresolve(str)
        assert p1 == "POOL"
        assert p1 is p2
        assert events == ["open"]  # opened once, survives the temp scope
        await c.aclose()
        assert events == ["open", "close"]  # closed at shutdown

    asyncio.run(main())


def test_async_propagates_up_to_a_sync_service():
    async def make_settings() -> Settings:
        return Settings()

    async def db_session():
        yield Db("y")

    async def main():
        c = Container()
        c.add_singleton_factory(Settings, make_settings)
        c.add_scoped_factory(Db, db_session)
        c.add_transient(Service)  # plain sync class, async deps
        async with c.ascope() as scope:
            svc = await scope.aresolve(Service)
            assert isinstance(svc, Service)
            assert isinstance(svc.db, Db)
            assert isinstance(svc.settings, Settings)

    asyncio.run(main())


def test_sync_resolve_rejects_async_factory():
    async def make_settings() -> Settings:
        return Settings()

    c = Container()
    c.add_singleton_factory(Settings, make_settings)
    c.add_transient(Service)
    c.add_scoped_factory(Db, _noop_async_gen)

    with pytest.raises(AsyncResolutionRequiredException):
        c.resolve(Settings)
    # Async dependency anywhere in the graph also forces the async path.
    with pytest.raises(AsyncResolutionRequiredException):
        c.resolve(Service)


async def _noop_async_gen():
    yield Db("z")


def test_async_cycle_is_detected():
    async def main():
        c = Container()
        c.add_transient(CycleA)
        c.add_transient(CycleB)
        with pytest.raises(CyclicDependencyException):
            await c.aresolve(CycleA)

    asyncio.run(main())


def test_singleton_resource_reopens_after_aclose():
    events = []

    async def resource():
        events.append("open")
        try:
            yield object()
        finally:
            events.append("close")

    async def main():
        c = Container()
        c.add_singleton_factory(object, resource)
        a = await c.aresolve(object)
        await c.aclose()
        # aclose evicts the finalized singleton; the next resolve must reopen,
        # not hand back the closed instance.
        b = await c.aresolve(object)
        assert a is not b
        assert events == ["open", "close", "open"]
        await c.aclose()
        assert events == ["open", "close", "open", "close"]

    asyncio.run(main())


def test_aresolve_sync_graph_matches_sync_resolve():
    # A graph with no factories at all has no async work; aresolve must return an
    # equivalent object and share singletons with the sync resolve path.
    c = Container()
    settings = Settings()
    c.add_instance(Settings, settings)

    class ApiClient:
        def __init__(self, s: Settings):
            self.s = s

    class Svc:
        def __init__(self, client: ApiClient):
            self.client = client

    c.add_singleton(ApiClient)
    c.add_transient(Svc)

    async def run():
        a = await c.aresolve(Svc)
        async with c.ascope() as scope:
            b = await scope.aresolve(Svc)
        sync = c.resolve(Svc)
        assert isinstance(a, Svc) and isinstance(b, Svc)
        assert a is not b  # transient
        # singleton ApiClient shared across aresolve, scope.aresolve, resolve
        assert a.client is b.client is sync.client
        assert a.client.s is settings

    asyncio.run(run())


def test_assert_valid_accepts_async_factories():
    async def make_settings() -> Settings:
        return Settings()

    async def db_session(settings: Settings):
        yield Db("v")

    c = Container()
    c.add_singleton_factory(Settings, make_settings)
    c.add_scoped_factory(Db, db_session)
    c.add_transient(Service)
    c.assert_valid()  # should not raise: every dependency is registered


def test_async_singleton_built_once_under_concurrent_resolve():
    builds = []

    async def make_pool() -> object:
        builds.append(1)
        await asyncio.sleep(0.005)  # suspend mid-build to widen the race window
        return object()

    async def main():
        c = Container()
        c.add_singleton_factory(object, make_pool)
        results = await asyncio.gather(*[c.aresolve(object) for _ in range(16)])
        assert sum(builds) == 1, f"built {sum(builds)} times"
        assert len({id(r) for r in results}) == 1  # all got the same instance

    asyncio.run(main())
