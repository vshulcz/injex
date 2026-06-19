"""Async interpreted-path branches: property injection, optional/default deps,
and container injection — the sync suite covers these, the async path didn't."""

import asyncio

from injex import Container, inject


class Settings:
    pass


def _async_settings_container() -> Container:
    async def make_settings() -> Settings:
        await asyncio.sleep(0)
        return Settings()

    c = Container()
    c.add_singleton_factory(Settings, make_settings)  # forces the async path
    return c


def test_async_property_injection():
    class Service:
        @inject
        def settings(self) -> Settings:  # property injection sets this attribute
            raise NotImplementedError

    async def main():
        c = _async_settings_container()
        c.add_transient(Service)
        service = await c.aresolve(Service)
        assert isinstance(service.settings, Settings)

    asyncio.run(main())


def test_async_optional_dependency_missing_is_none():
    class Cache:
        pass

    class Service:
        def __init__(self, settings: Settings, cache: Cache | None = None):
            self.settings = settings
            self.cache = cache

    async def main():
        c = _async_settings_container()
        c.add_transient(Service)  # Cache never registered
        service = await c.aresolve(Service)
        assert isinstance(service.settings, Settings)
        assert service.cache is None

    asyncio.run(main())


def test_async_default_value_used_when_unregistered():
    class Service:
        def __init__(self, settings: Settings, retries: int = 3):
            self.settings = settings
            self.retries = retries

    async def main():
        c = _async_settings_container()
        c.add_transient(Service)
        assert (await c.aresolve(Service)).retries == 3

    asyncio.run(main())


def test_async_container_injection():
    class Service:
        def __init__(self, settings: Settings, container):  # unannotated -> container
            self.settings = settings
            self.container = container

    async def main():
        c = _async_settings_container()
        c.add_transient(Service)
        service = await c.aresolve(Service)
        assert service.container is c

    asyncio.run(main())
