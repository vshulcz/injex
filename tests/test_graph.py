"""container.graph() renders the wiring as text / Mermaid / DOT without building
anything, marking unregistered dependencies."""

import pytest

from injex import Container


class Config: ...


class Session: ...


class Repo:
    def __init__(self, cfg: Config, session: Session) -> None:  # Session unregistered
        self.cfg = cfg
        self.session = session


class Service:
    def __init__(self, repo: Repo) -> None:
        self.repo = repo


def _container() -> Container:
    c = Container()
    c.add_singleton(Config)
    c.add_transient(Repo)
    c.add_transient(Service)
    return c


def test_text_graph_shows_edges_lifestyles_and_gaps():
    text = _container().graph()
    assert "Config [singleton]" in text
    assert "Repo [transient]" in text
    assert "-> Config" in text
    assert "-> Session (unregistered)" in text
    assert "-> Repo" in text


def test_mermaid_graph_uses_solid_and_dashed_edges():
    mermaid = _container().graph("mermaid")
    assert mermaid.startswith("flowchart TD")
    assert "-->" in mermaid  # registered edge
    assert "-.->" in mermaid  # unregistered edge (Session)


def test_dot_graph_is_a_digraph_with_dashed_gaps():
    dot = _container().graph("dot")
    assert dot.startswith("digraph injex {")
    assert '"Repo" -> "Config";' in dot
    assert "[style=dashed]" in dot  # unregistered Session
    assert dot.rstrip().endswith("}")


def test_instance_registration_is_labelled():
    c = Container()
    c.add_instance(Config, Config())
    assert "Config [instance]" in c.graph()


def test_unknown_format_raises():
    with pytest.raises(ValueError, match="unknown graph format"):
        _container().graph("svg")


def test_empty_container_graphs_are_empty_but_valid():
    c = Container()
    assert c.graph() == ""
    assert c.graph("mermaid") == "flowchart TD"
    assert c.graph("dot").startswith("digraph injex {")
