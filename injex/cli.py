"""Command line entry point: ``python -m injex check <module>:<attr>``.

Validates a container's dependency graph in CI without constructing anything,
exiting non-zero when the graph is incomplete. Standard library only."""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from typing import Any

from .container import Container


def _load_container(spec: str) -> Container:
    if ":" not in spec:
        raise SystemExit(
            f"error: target must be 'module:attribute', got {spec!r} "
            "(e.g. 'myapp.bootstrap:container')"
        )
    module_name, _, attr = spec.partition(":")

    # Make the current directory importable so a project's own module resolves
    # whether invoked as `python -m injex` or via the `injex` console script.
    cwd = os.getcwd()
    if cwd not in sys.path:  # pragma: no cover - depends on how python was invoked
        sys.path.insert(0, cwd)

    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        raise SystemExit(f"error: could not import '{module_name}': {exc}") from exc

    try:
        target: Any = getattr(module, attr)
    except AttributeError:
        raise SystemExit(f"error: '{module_name}' has no attribute '{attr}'") from None

    # Accept a Container directly, or a zero-argument factory that returns one.
    if callable(target) and not isinstance(target, Container):
        target = target()
    if not isinstance(target, Container):
        raise SystemExit(
            f"error: '{spec}' is not a Container (got {type(target).__name__})"
        )
    return target


def _check(spec: str) -> int:
    container = _load_container(spec)
    errors = container.validate()
    if not errors:
        print(f"OK: {spec} — dependency graph is valid")
        return 0
    print(f"FAIL: {spec} — {len(errors)} error(s):", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="injex",
        description="Validate an Injex container's dependency graph.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    check = subcommands.add_parser(
        "check",
        help="Validate a container without constructing services (for CI).",
    )
    check.add_argument(
        "target",
        help="Container to validate, as 'module:attribute' "
        "(e.g. 'myapp.bootstrap:container').",
    )
    args = parser.parse_args(argv)
    return _check(args.target)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
