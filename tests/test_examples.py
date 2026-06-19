"""Import every example so they can't silently rot as the API changes.

FastAPI examples are skipped unless FastAPI is installed; the rest must import
and run their module-level code without error.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
_NEEDS_FASTAPI = {"fastapi_app", "fastapi_async", "fastapi_lifespan", "fastapi_ext"}

example_files = sorted(p for p in EXAMPLES.glob("*.py") if p.stem != "__init__")


@pytest.mark.parametrize("path", example_files, ids=lambda p: p.stem)
def test_example_runs(path: Path, monkeypatch, tmp_path) -> None:
    if path.stem in _NEEDS_FASTAPI and importlib.util.find_spec("fastapi") is None:
        pytest.skip("FastAPI not installed")

    # Run in a temp dir so examples that write files don't litter the repo.
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location(f"example_{path.stem}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
