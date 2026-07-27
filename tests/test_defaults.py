"""Constructor defaults and partial construction — the most common "why won't
this wire" friction. A parameter with a default is not a missing dependency, and
call() can construct a class with some arguments supplied by hand."""

from injex import Container


def test_resolve_uses_constructor_default_when_dependency_is_unregistered():
    class Cache: ...

    class Service:
        def __init__(self, cache: "Cache | None" = None, retries: int = 3):
            self.cache = cache
            self.retries = retries

    c = Container()
    c.add_transient(Service)

    assert c.validate() == []  # a default is not a missing dependency
    service = c.resolve(Service)
    assert service.cache is None
    assert service.retries == 3


def test_registered_dependency_wins_over_a_default():
    class Cache: ...

    class Service:
        def __init__(self, cache: Cache | None = None):
            self.cache = cache

    c = Container()
    c.add_singleton(Cache)
    c.add_transient(Service)

    assert isinstance(c.resolve(Service).cache, Cache)


def test_call_constructs_a_class_with_partial_kwargs():
    class DB: ...

    class Repo:
        def __init__(self, db: DB, table: str):
            self.db = db
            self.table = table

    c = Container()
    c.add_singleton(DB)

    repo = c.call(Repo, table="users")
    assert isinstance(repo.db, DB)
    assert repo.table == "users"
