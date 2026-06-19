"""CLI injection: Inject() + wire(), exercised with a real Click command."""

import inspect

import click
from click.testing import CliRunner

from injex import Container
from injex.ext.cli import Inject, wire


class Greeter:
    def greet(self, name: str) -> str:
        return f"hello {name}"


def test_wire_hides_injected_params_from_signature():
    c = Container()
    c.add_singleton(Greeter)

    @wire(c)
    def cmd(name: str, greeter: Greeter = Inject()) -> str:
        return greeter.greet(name)

    assert list(inspect.signature(cmd).parameters) == ["name"]  # greeter hidden
    assert cmd("ada") == "hello ada"  # greeter injected


def test_wire_with_real_click_command():
    container = Container()
    container.add_singleton(Greeter)

    @click.command()
    @click.argument("name")
    @wire(container)
    def greet(name: str, greeter: Greeter = Inject()) -> None:
        click.echo(greeter.greet(name))

    result = CliRunner().invoke(greet, ["ada"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "hello ada"


def test_wire_injects_container_and_respects_overrides():
    container = Container()
    container.add_singleton(Greeter)

    @wire(container)
    def cmd(name: str, greeter: Greeter = Inject(), suffix: str = "!") -> str:
        return greeter.greet(name) + suffix

    # suffix stays a normal (visible) parameter; greeter is injected.
    assert list(inspect.signature(cmd).parameters) == ["name", "suffix"]
    assert cmd("bob", suffix="?") == "hello bob?"
