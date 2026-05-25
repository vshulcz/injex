# Contributing to Injex

Thanks for improving Injex. The project favors small, well-tested changes that
keep the container easy to understand.

## Local setup

```bash
git clone https://github.com/vshulcz/injex.git
cd injex
uv sync
```

Run the quality checks before opening a pull request:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy injex tests
uv run pytest
```

Use `uv run ruff format .` to format changed files.

## Good first contributions

- Improve examples for common application patterns.
- Add tests for edge cases around factories, scopes, and optional dependencies.
- Improve type hints without expanding the public API unnecessarily.
- Clarify documentation where the current behavior is correct but not obvious.

## Pull request guidelines

- Keep the change focused. One behavior change per PR is easier to review.
- Add or update tests for code changes.
- Update README or `docs/tutorial.md` when public behavior changes.
- Avoid new runtime dependencies unless there is a strong reason.
- Prefer explicit APIs over magic.

## Design principles

Injex should remain:

- small enough to read in one sitting;
- predictable under tests;
- useful outside any single web framework;
- compatible with normal Python type hints;
- dependency-free at runtime.

If a proposed feature needs a lot of policy or hidden behavior, open an issue
first so the API shape can be discussed.
