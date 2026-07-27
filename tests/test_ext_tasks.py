"""injex.ext.tasks.inject / ainject: scope-per-call injection for task and
handler functions, framework-agnostic (Celery, arq, aiogram, ...)."""

import asyncio
import inspect

import pytest

from injex import Container
from injex.ext.cli import Inject
from injex.ext.tasks import ainject, inject


def test_inject_requires_a_type_annotation():
    container = Container()

    with pytest.raises(TypeError, match="no type annotation"):

        @inject(container)
        def task(order_id: int, thing=Inject()):  # thing has no annotation
            return thing


class Orders:
    def __init__(self) -> None:
        self.processed: list[int] = []

    def process(self, order_id: int) -> None:
        self.processed.append(order_id)


def test_inject_resolves_service_and_hides_it_from_the_signature():
    container = Container()
    container.add_singleton(Orders)

    @inject(container)
    def task(order_id: int, orders: Orders = Inject()) -> Orders:
        orders.process(order_id)
        return orders

    # The runner only sees the non-injected parameter.
    assert list(inspect.signature(task).parameters) == ["order_id"]

    orders = task(7)
    assert orders.processed == [7]


def test_inject_opens_a_scope_per_call_and_finalizes_resources():
    events: list[str] = []

    class Session: ...

    def open_session():
        events.append("open")
        try:
            yield Session()
        finally:
            events.append("close")

    class Work:
        def __init__(self, session: Session) -> None:
            self.session = session

    container = Container()
    container.add_scoped_factory(Session, open_session)
    container.add_transient(Work)

    @inject(container)
    def task(work: Work = Inject()) -> None:
        events.append("run")

    task()
    task()
    # each call opens and closes its own scope
    assert events == ["open", "run", "close", "open", "run", "close"]


def test_ainject_awaits_and_injects_into_an_async_handler():
    events: list[str] = []

    class Session: ...

    async def open_session():
        events.append("open")
        try:
            yield Session()
        finally:
            events.append("close")

    class UserService:
        def __init__(self, session: Session) -> None:
            self.session = session

    container = Container()
    container.add_scoped_factory(Session, open_session)
    container.add_transient(UserService)

    @ainject(container)
    async def handle(message: str, users: UserService = Inject()) -> str:
        events.append(f"handle:{message}")
        return message.upper()

    assert list(inspect.signature(handle).parameters) == ["message"]
    result = asyncio.run(handle("hi"))
    assert result == "HI"
    assert events == ["open", "handle:hi", "close"]
