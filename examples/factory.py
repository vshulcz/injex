"""A factory builds a service when construction needs logic the constructor
can't express. The factory's own parameters are injected too."""

from injex import Container


class Settings:
    def __init__(self) -> None:
        self.pool_size = 5


class ConnectionPool:
    def __init__(self, size: int) -> None:
        self.size = size


def make_pool(settings: Settings) -> ConnectionPool:
    # `settings` is injected; the factory turns it into the constructor argument.
    return ConnectionPool(size=settings.pool_size)


def main() -> None:
    container = Container()
    container.add_instance(Settings, Settings())
    container.add_singleton_factory(ConnectionPool, make_pool)
    container.assert_valid()

    pool = container.resolve(ConnectionPool)
    assert pool.size == 5
    print("pool size from settings:", pool.size)


if __name__ == "__main__":
    main()
