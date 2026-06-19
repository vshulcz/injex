"""Auto-registration: mark classes with @injectable, register them with scan().

In a real app the services live in their own module(s) and you call
``container.scan(myapp.services)``. Here they live in this module, so we scan it.
"""

import sys

from injex import Container, injectable


class Settings:
    def __init__(self) -> None:
        self.url = "postgres://db"


@injectable(lifestyle="singleton")
class ApiClient:
    def __init__(self, settings: Settings):
        self.settings = settings


@injectable  # transient by default
class UserRepository:
    def __init__(self, client: ApiClient):
        self.client = client


def main() -> None:
    container = Container()
    container.add_instance(Settings, Settings())
    container.scan(sys.modules[__name__])  # registers the @injectable classes above
    container.assert_valid()

    repo = container.resolve(UserRepository)
    assert isinstance(repo.client, ApiClient)
    assert repo.client.settings.url == "postgres://db"
    print("scanned and resolved:", repo.client.settings.url)


if __name__ == "__main__":
    main()
