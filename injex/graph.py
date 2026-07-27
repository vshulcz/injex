"""Render a container's dependency graph as text, Mermaid, or Graphviz DOT.

Pure string emission, zero dependencies — print it, commit it, or paste it into
a Mermaid/Graphviz renderer. The container builds the node list; these functions
only format it."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GraphNode:
    label: str
    kind: str  # lifestyle ("singleton"/"transient"/"scoped") or "instance"
    # (dependency label, is it registered, is it optional/defaulted)
    deps: tuple[tuple[str, bool, bool], ...]


def _dep_suffix(registered: bool, optional: bool) -> str:
    if registered:
        return ""
    return " (optional, unregistered)" if optional else " (unregistered)"


def to_text(nodes: list[GraphNode]) -> str:
    lines: list[str] = []
    for node in nodes:
        lines.append(f"{node.label} [{node.kind}]")
        for label, registered, optional in node.deps:
            lines.append(f"    -> {label}{_dep_suffix(registered, optional)}")
    return "\n".join(lines)


def _ids(nodes: list[GraphNode]) -> dict[str, str]:
    ids: dict[str, str] = {}
    for node in nodes:
        ids.setdefault(node.label, f"n{len(ids)}")
        for label, _registered, _optional in node.deps:
            ids.setdefault(label, f"n{len(ids)}")
    return ids


def to_mermaid(nodes: list[GraphNode]) -> str:
    ids = _ids(nodes)
    lines = ["flowchart TD"]
    for label, node_id in ids.items():
        lines.append(f'    {node_id}["{label}"]')
    for node in nodes:
        for label, registered, _optional in node.deps:
            arrow = "-->" if registered else "-.->"
            lines.append(f"    {ids[node.label]} {arrow} {ids[label]}")
    return "\n".join(lines)


def to_dot(nodes: list[GraphNode]) -> str:
    lines = ["digraph injex {", "    rankdir=LR;"]
    seen: set[str] = set()
    for node in nodes:
        for label in (node.label, *(dep[0] for dep in node.deps)):
            if label not in seen:
                seen.add(label)
                lines.append(f'    "{label}";')
    for node in nodes:
        for label, registered, _optional in node.deps:
            style = "" if registered else " [style=dashed]"
            lines.append(f'    "{node.label}" -> "{label}"{style};')
    lines.append("}")
    return "\n".join(lines)


_RENDERERS = {"text": to_text, "mermaid": to_mermaid, "dot": to_dot}


def render(nodes: list[GraphNode], fmt: str) -> str:
    try:
        renderer = _RENDERERS[fmt]
    except KeyError:
        raise ValueError(
            f"unknown graph format {fmt!r}; use 'text', 'mermaid', or 'dot'"
        ) from None
    return renderer(nodes)
