"""CLI command with injected services via injex.ext.cli.

Run: pip install click; python -m examples.cli_injection greet ada
"""

import click

from injex import Container
from injex.ext.cli import Inject, wire


class Greeter:
    def greet(self, name: str) -> str:
        return f"hello, {name}"


container = Container()
container.add_singleton(Greeter)


@click.command()
@click.argument("name")
@wire(container)
def greet(name: str, greeter: Greeter = Inject()) -> None:
    click.echo(greeter.greet(name))


if __name__ == "__main__":
    greet()
