"""Fixtures for the CLI tests: a valid container, a broken one, a factory, and
a non-container attribute."""

from injex import Container


class Config: ...


class Client:
    def __init__(self, config: Config) -> None:
        self.config = config


class Missing: ...


class Broken:
    def __init__(self, missing: Missing) -> None:  # Missing is never registered
        self.missing = missing


container = Container()
container.add_singleton(Config)
container.add_singleton(Client)

broken = Container()
broken.add_transient(Broken)


def make_container() -> Container:
    return container


not_a_container = 42
