"""Per-request scope benchmark: open a scope, resolve a use-case whose graph has
a request-scoped session, close the scope. That is the shape a web request hits.

Injex vs hand-written wiring only. A fair cross-library scope comparison is hard
because scope semantics differ, so this measures the overhead Injex adds over
doing the same request-scoped wiring by hand. Synthetic and graph-specific;
measure your own app.

    uv run python benchmarks/resolve_scoped.py
"""

import gc
import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from injex import Container


class Settings:
    dsn: str = "sqlite:///:memory:"


class ApiClient:
    def __init__(self, settings: Settings):
        self.settings = settings


class Session:  # request-scoped: one per scope
    def __init__(self, client: ApiClient):
        self.client = client


class UserRepository:
    def __init__(self, session: Session):
        self.session = session


class RegisterUser:
    def __init__(self, repo: UserRepository):
        self.repo = repo


settings = Settings()
app_client = ApiClient(settings)  # singleton, shared across requests


def manual_request() -> RegisterUser:
    session = Session(app_client)  # one session per request
    return RegisterUser(UserRepository(session))


def setup_injex() -> Callable[[], RegisterUser]:
    container = Container()
    container.add_instance(Settings, settings)
    container.add_singleton(ApiClient)
    container.add_scoped(Session)
    container.add_transient(UserRepository)
    container.add_transient(RegisterUser)
    container.assert_valid()

    def request() -> RegisterUser:
        with container.create_scope() as scope:
            return scope.resolve(RegisterUser)

    request()
    return request


def bench(
    name: str,
    fn: Callable[[], object],
    *,
    iterations: int = 250_000,
    rounds: int = 9,
) -> tuple[str, float, float, float]:
    for _ in range(12_000):
        fn()

    samples = []
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(rounds):
            start = time.perf_counter_ns()
            for _ in range(iterations):
                obj = fn()
            end = time.perf_counter_ns()
            assert obj is not None
            samples.append((end - start) / iterations)
    finally:
        if gc_was_enabled:
            gc.enable()

    return name, statistics.median(samples), min(samples), max(samples)


def main() -> None:
    cases = [("manual", manual_request), ("injex", setup_injex())]
    results = [bench(name, fn) for name, fn in cases]
    baseline = dict((name, median) for name, median, _, _ in results)["manual"]

    print("Per-request scope: open scope + resolve + close")
    print(f"{'library':<10} {'median µs/op':>14} {'x manual':>10} {'min..max µs':>18}")
    for name, median, min_value, max_value in sorted(results, key=lambda row: row[1]):
        print(
            f"{name:<10} {median / 1000:>14.3f} {median / baseline:>10.2f} "
            f"{min_value / 1000:>8.3f}..{max_value / 1000:<8.3f}"
        )


if __name__ == "__main__":
    main()
