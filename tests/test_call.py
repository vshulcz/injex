"""container.call() / acall(): invoke a function with injected dependencies."""

import asyncio

import pytest

from injex import Container, ServiceNotRegisteredException


class Repo:
    pass


class Service:
    def __init__(self, repo: Repo):
        self.repo = repo


def _container() -> Container:
    c = Container()
    c.add_singleton(Repo)
    c.add_transient(Service)
    return c


def test_call_injects_and_overrides():
    c = _container()

    def handle(email: str, service: Service) -> tuple[str, Service]:
        return email, service

    email, service = c.call(handle, email="a@b.c")
    assert email == "a@b.c"
    assert isinstance(service, Service)


def test_call_injects_container():
    c = _container()

    def needs(container) -> bool:
        return container is c

    assert c.call(needs) is True


def test_call_respects_defaults_and_optional():
    c = _container()

    def handle(service: Service, page: int = 1) -> int:
        return page

    assert c.call(handle) == 1
    assert c.call(handle, page=5) == 5


def test_call_missing_dependency_raises_clear_error():
    c = Container()  # Repo not registered

    def handle(service: Service) -> None: ...

    with pytest.raises(ServiceNotRegisteredException) as exc:
        c.call(handle)
    message = str(exc.value)
    assert "Service" in message
    assert "handle.service" in message  # error names the function parameter


def test_acall_awaits_async_dependency_and_coroutine():
    async def make_repo() -> Repo:
        await asyncio.sleep(0)
        return Repo()

    async def main():
        c = Container()
        c.add_singleton_factory(Repo, make_repo)
        c.add_transient(Service)

        async def handle(tag: str, service: Service) -> str:
            return f"{tag}:{type(service.repo).__name__}"

        return await c.acall(handle, tag="x")

    assert asyncio.run(main()) == "x:Repo"


def test_acall_finalizes_async_resources_after_call():
    events = []

    async def session():
        events.append("open")
        try:
            yield object()
        finally:
            events.append("close")

    async def run():
        c = Container()
        c.add_scoped_factory(object, session)

        async def handle(s: object) -> str:
            assert events == ["open"]  # resource open during the call
            return "ok"

        out = await c.acall(handle)
        assert out == "ok"
        assert events == ["open", "close"]  # finalized when acall returned

    asyncio.run(run())
