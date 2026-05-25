from dataclasses import dataclass

from injex import Container


@dataclass(frozen=True)
class Settings:
    api_url: str
    token: str


class ApiClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def fetch_status(self) -> str:
        return f"connected to {self.settings.api_url}"


class StatusCommand:
    def __init__(self, client: ApiClient):
        self.client = client

    def run(self) -> None:
        print(self.client.fetch_status())


def build_container() -> Container:
    container = Container()
    container.add_instance(
        Settings,
        Settings(api_url="https://api.example.com", token="dev-token"),
    )
    container.add_singleton(ApiClient)
    container.add_transient(StatusCommand)
    return container


if __name__ == "__main__":
    container = build_container()
    container.resolve(StatusCommand).run()
