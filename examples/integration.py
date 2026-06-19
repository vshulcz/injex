"""One graph combining several features: a factory-built scoped dependency, an
optional dependency, and property injection — resolved inside a scope."""

from typing import Protocol

from injex import Container, inject


class Database(Protocol):
    def query(self, sql: str) -> str: ...


class PostgresDatabase:
    def query(self, sql: str) -> str:
        return f"postgres: {sql}"


class Cache(Protocol):
    def get(self, key: str) -> str | None: ...


class MemoryCache:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.store.get(key)


class Logger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def log(self, message: str) -> None:
        self.messages.append(message)


class DataService:
    def __init__(self, db: Database, cache: Cache | None = None):
        self.db = db
        self.cache = cache

    @inject
    def logger(self) -> Logger:  # property injection
        ...

    def get(self, key: str) -> str:
        if self.cache is not None:
            self.cache.get(key)
        result = self.db.query(f"select * from data where key = '{key}'")
        self.logger.log(f"read {key}")
        return result


def make_database() -> Database:
    # In a real app the implementation is chosen from config or env.
    return PostgresDatabase()


def main() -> None:
    container = Container()
    container.add_scoped_factory(Database, make_database)
    container.add_singleton(Cache, MemoryCache)
    container.add_singleton(Logger)
    container.add_transient(DataService)
    container.assert_valid()

    with container.create_scope() as scope:
        service = scope.resolve(DataService)
        print(service.get("alice"))
        print("logged:", service.logger.messages)


if __name__ == "__main__":
    main()
