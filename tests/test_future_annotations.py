"""`from __future__ import annotations` (PEP 563) turns every annotation into a
string. Injection must still work, and — crucially for the validate-before-start
guarantee — validate() and resolve() must agree even when one annotation in a
signature cannot be resolved."""

import pytest

from injex import Container
from injex.errors import ServiceNotRegisteredException
from tests import _future_annotations_app as app


def test_resolves_a_string_annotated_graph():
    container = Container()
    container.add_singleton(app.Database)
    container.add_singleton(app.Repo)
    container.add_transient(app.Service)

    assert container.validate() == []
    service = container.resolve(app.Service)
    assert isinstance(service.repo, app.Repo)
    assert isinstance(service.repo.db, app.Database)


def test_one_unresolvable_annotation_does_not_break_its_siblings():
    """A single unresolvable annotation (here a name that only exists as a
    forward reference) must not stop the other, registered dependency from
    resolving, and validate()/resolve() must point at the same problem."""
    container = Container()
    container.add_singleton(app.Mailer)
    container.add_transient(app.Handler)

    errors = container.validate()
    messages = [error.message for error in errors]

    # The unresolvable dependency is reported...
    assert any("Ghost" in message for message in messages)
    # ...and the good, registered sibling is NOT falsely flagged.
    assert all("Mailer" not in message for message in messages)

    # resolve() fails on the SAME dependency validate() flagged, not on the
    # good sibling — the two never disagree.
    with pytest.raises(ServiceNotRegisteredException) as excinfo:
        container.resolve(app.Handler)
    assert "Ghost" in str(excinfo.value)
