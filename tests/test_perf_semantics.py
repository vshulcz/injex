"""Semantics that the compiled fast paths must preserve.

These pin the behaviours the constant-inlining / cache-check optimisations could
plausibly break: singleton identity and single-construction across every resolve
entry point, laziness (only graphs that are actually resolved construct their
singletons), and correct rebuild after an override.
"""

import asyncio

from injex import Container


class Settings:
    instances = 0

    def __init__(self) -> None:
        Settings.instances += 1


class ApiClient:
    def __init__(self, settings: Settings):
        self.settings = settings


class Repo:
    def __init__(self, client: ApiClient):
        self.client = client


class Service:
    def __init__(self, repo: Repo, client: ApiClient):
        self.repo = repo
        self.client = client


def _container() -> Container:
    Settings.instances = 0
    c = Container()
    c.add_singleton(Settings)
    c.add_singleton(ApiClient)
    c.add_transient(Repo)
    c.add_transient(Service)
    return c


def test_singleton_inlined_but_constructed_once():
    c = _container()
    a = c.resolve(Service)
    b = c.resolve(Service)
    assert a is not b  # transient root
    # the shared singleton is the same object and was built exactly once
    assert a.client is b.client
    assert a.repo.client is a.client
    assert Settings.instances == 1


def test_singleton_identity_across_entry_points():
    c = _container()
    s_root = c.resolve(Service)
    scoped = c.create_scope().resolve(Service)
    aresolved = asyncio.run(c.aresolve(Service))

    # ApiClient singleton is identical no matter how Service was resolved
    assert s_root.client is scoped.client is aresolved.client
    # Settings singleton still built once across all three paths
    assert Settings.instances == 1


def test_singleton_root_returns_same_instance():
    c = _container()
    a = c.resolve(ApiClient)
    b = c.resolve(ApiClient)
    assert a is b
    assert a is c.create_scope().resolve(ApiClient)
    assert a is asyncio.run(c.aresolve(ApiClient))


def test_unresolved_singletons_are_not_eagerly_built():
    # Resolving Repo must not construct a singleton that only Service needs...
    Settings.instances = 0
    c = Container()
    c.add_singleton(Settings)
    c.add_singleton(ApiClient)
    c.add_transient(Repo)

    class Unrelated:
        def __init__(self) -> None:
            raise AssertionError("must not be constructed")

    c.add_singleton(Unrelated)

    c.resolve(Repo)  # only needs ApiClient -> Settings
    assert Settings.instances == 1  # built, because Repo needs it
    # Unrelated never resolved -> never constructed (no eager realization leak)


def test_override_after_warmup_rebuilds():
    c = _container()
    first = c.resolve(Service)
    real_client = first.client

    fake = ApiClient(Settings())
    with c.override(ApiClient, instance=fake):
        during = c.resolve(Service)
        assert during.client is fake  # inlined creator rebuilt with the override

    after = c.resolve(Service)
    assert after.client is real_client  # restored, not the fake
    assert after.client is not fake


def test_async_cached_singleton_path():
    async def make_settings() -> Settings:
        return Settings()

    async def main():
        Settings.instances = 0
        c = Container()
        c.add_singleton_factory(Settings, make_settings)
        c.add_singleton(ApiClient)
        c.add_transient(Repo)
        c.add_transient(Service)

        a = await c.aresolve(Service)
        b = await c.aresolve(Service)
        assert a is not b  # transient root
        assert a.client is b.client  # async-derived singleton shared
        assert a.client.settings is b.client.settings
        assert Settings.instances == 1  # async singleton awaited/built once

    asyncio.run(main())
