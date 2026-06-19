"""Injecting named registrations into constructors via Annotated[T, Named(...)]."""

import asyncio
from typing import Annotated

from injex import Container, Named


class DB:
    pass


class Primary(DB):
    pass


class Replica(DB):
    pass


def _two_db_container() -> Container:
    c = Container()
    c.add_singleton(DB, Primary, name="primary")
    c.add_singleton(DB, Replica, name="replica")
    return c


def test_named_dependency_selects_registration():
    class Service:
        def __init__(self, db: Annotated[DB, Named("replica")]):
            self.db = db

    c = _two_db_container()
    c.add_transient(Service)
    assert isinstance(c.resolve(Service).db, Replica)


def test_two_named_dependencies_in_one_constructor():
    class Service:
        def __init__(
            self,
            read: Annotated[DB, Named("replica")],
            write: Annotated[DB, Named("primary")],
        ):
            self.read = read
            self.write = write

    c = _two_db_container()
    c.add_transient(Service)
    s = c.resolve(Service)
    assert isinstance(s.read, Replica)
    assert isinstance(s.write, Primary)


def test_named_dependency_in_scope_and_async():
    class Service:
        def __init__(self, db: Annotated[DB, Named("primary")]):
            self.db = db

    c = _two_db_container()
    c.add_transient(Service)

    with c.create_scope() as scope:
        assert isinstance(scope.resolve(Service).db, Primary)

    assert isinstance(asyncio.run(c.aresolve(Service)).db, Primary)


def test_optional_named_dependency_missing_is_none():
    class Service:
        def __init__(self, db: Annotated[DB, Named("missing")] | None = None):
            self.db = db

    c = _two_db_container()
    c.add_transient(Service)
    assert c.resolve(Service).db is None


def test_validate_accepts_registered_named_dependency():
    class Service:
        def __init__(self, db: Annotated[DB, Named("primary")]):
            self.db = db

    c = _two_db_container()
    c.add_transient(Service)
    assert c.validate() == []


def test_validate_reports_missing_named_dependency():
    class Service:
        def __init__(self, db: Annotated[DB, Named("nope")]):
            self.db = db

    c = _two_db_container()
    c.add_transient(Service)
    errors = c.validate()
    assert len(errors) == 1
