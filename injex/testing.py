"""Test helpers. Opt-in: ``from injex.testing import overrides``.

``container.override(...)`` already swaps one binding and restores it on exit,
in sync, async, scoped and nested contexts. ``overrides`` applies several at
once with a single restore, which reads cleanly inside a pytest fixture::

    import pytest
    from injex.testing import overrides

    @pytest.fixture
    def container():
        return build_container()  # your application's container

    def test_registration(container):
        with overrides(container, {Mailer: FakeMailer(), Clock: FrozenClock()}):
            container.resolve(RegisterUser).execute("ada@example.com")
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import ExitStack, contextmanager
from typing import Any

from .container import Container


@contextmanager
def overrides(
    container: Container, mapping: Mapping[Any, Any] | None = None
) -> Iterator[Container]:
    """Temporarily replace several bindings with instances, restoring every one
    on exit (LIFO). ``mapping`` maps an interface to the instance to inject."""
    with ExitStack() as stack:
        for interface, instance in (mapping or {}).items():
            stack.enter_context(container.override(interface, instance=instance))
        yield container
