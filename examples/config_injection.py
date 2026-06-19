"""Configuration is just a dependency in Injex — no separate config DSL.

Two ways to inject it: a whole settings object, or individual named values.
"""

from dataclasses import dataclass
from typing import Annotated

from injex import Container, Named


@dataclass
class Settings:
    database_url: str
    smtp_url: str


# 1. Inject the settings object.
class Reporting:
    def __init__(self, settings: Settings):
        self.dsn = settings.database_url


# 2. Inject an individual value by name.
class Mailer:
    def __init__(self, smtp: Annotated[str, Named("smtp_url")]):
        self.smtp = smtp


def main() -> None:
    settings = Settings(database_url="postgres://db", smtp_url="smtp://mail")

    container = Container()
    container.add_instance(Settings, settings)
    container.add_instance(str, settings.smtp_url, name="smtp_url")
    container.add_transient(Reporting)
    container.add_transient(Mailer)
    container.assert_valid()

    assert container.resolve(Reporting).dsn == "postgres://db"
    assert container.resolve(Mailer).smtp == "smtp://mail"
    print("config injected:", container.resolve(Mailer).smtp)


if __name__ == "__main__":
    main()
