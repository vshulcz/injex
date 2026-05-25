# Releasing Injex

This checklist keeps releases small, repeatable, and easy to audit.

## Before tagging

1. Update `CHANGELOG.md` and keep the version section clear for users.
2. Update `pyproject.toml` and `uv.lock` to the same version.
3. Run local checks:

   ```bash
   uv run ruff format --check .
   uv run ruff check .
   uv run mypy injex tests
   uv run pytest
   uv build
   ```

4. Install the built wheel in a clean environment and run a small import/resolve
   smoke test.

## Tagging

Use annotated version tags:

```bash
git tag -a v1.2.0 -m "Release v1.2.0"
git push origin v1.2.0
```

The release workflow builds source and wheel distributions, smoke-tests the
wheel, uploads the artifacts, and attaches them to the GitHub release.

## PyPI

Publish to PyPI only after the GitHub release artifacts pass the smoke test.
Keep runtime dependencies empty unless a future release explicitly changes that
contract.
