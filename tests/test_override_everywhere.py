"""override() must work the same in sync, nested, scoped and async resolution,
and injex.testing.overrides applies several at once."""

import asyncio

from injex import Container
from injex.testing import overrides


class Mailer:
    def send(self) -> str:
        return "real"


class Fake:
    def send(self) -> str:
        return "fake"


class UseCase:
    def __init__(self, mailer: Mailer) -> None:
        self.mailer = mailer


def _container() -> Container:
    c = Container()
    c.add_singleton(Mailer)
    c.add_transient(UseCase)
    return c


def test_override_restores_afterwards():
    c = _container()
    assert c.resolve(UseCase).mailer.send() == "real"
    with c.override(Mailer, instance=Fake()):
        assert c.resolve(UseCase).mailer.send() == "fake"
    assert c.resolve(UseCase).mailer.send() == "real"


def test_nested_overrides_stack_and_unwind():
    c = _container()

    class Fake2:
        def send(self) -> str:
            return "fake2"

    with c.override(Mailer, instance=Fake()):
        with c.override(Mailer, instance=Fake2()):
            assert c.resolve(UseCase).mailer.send() == "fake2"
        assert c.resolve(UseCase).mailer.send() == "fake"
    assert c.resolve(UseCase).mailer.send() == "real"


def test_override_applies_inside_a_scope():
    c = _container()
    with c.override(Mailer, instance=Fake()), c.create_scope() as scope:
        assert scope.resolve(UseCase).mailer.send() == "fake"


def test_override_applies_to_async_resolution():
    async def go() -> tuple[str, str]:
        c = _container()
        with c.override(Mailer, instance=Fake()):
            during = (await c.aresolve(UseCase)).mailer.send()
        after = (await c.aresolve(UseCase)).mailer.send()
        return during, after

    during, after = asyncio.run(go())
    assert during == "fake"
    assert after == "real"


def test_overrides_helper_applies_several_and_restores():
    class Clock:
        def now(self) -> str:
            return "real-time"

    class FrozenClock:
        def now(self) -> str:
            return "frozen"

    class App:
        def __init__(self, mailer: Mailer, clock: Clock) -> None:
            self.mailer = mailer
            self.clock = clock

    c = Container()
    c.add_singleton(Mailer)
    c.add_singleton(Clock)
    c.add_transient(App)

    with overrides(c, {Mailer: Fake(), Clock: FrozenClock()}):
        app = c.resolve(App)
        assert app.mailer.send() == "fake"
        assert app.clock.now() == "frozen"

    restored = c.resolve(App)
    assert restored.mailer.send() == "real"
    assert restored.clock.now() == "real-time"
