"""Resources with teardown: a generator factory finalized when its scope exits
(scoped/transient) or on container.close() (singleton)."""

from collections.abc import Iterator

from injex import Container


class Settings:
    def __init__(self) -> None:
        self.url = "sqlite://"


class Session:
    def __init__(self, url: str) -> None:
        self.url = url
        self.closed = False

    def close(self) -> None:
        self.closed = True


def db_session(settings: Settings) -> Iterator[Session]:
    session = Session(settings.url)
    try:
        yield session  # handed to whoever resolves Session
    finally:
        session.close()  # runs when the scope exits


def main() -> None:
    container = Container()
    container.add_instance(Settings, Settings())
    container.add_scoped_factory(Session, db_session)

    with container.create_scope() as scope:
        session = scope.resolve(Session)
        assert not session.closed
    assert session.closed  # finalized on scope exit
    print("session closed on scope exit:", session.closed)


if __name__ == "__main__":
    main()
