"""Async resolution benchmark.

Two shapes, both on the same small service graph used by ``resolve_graph.py``:

1. *sync graph via the async API* — every service is a plain class, but it is
   resolved through each library's async container. This is the common FastAPI
   case: you ``await`` the resolve in a handler even though the services
   themselves are synchronous.
2. *graph with an async factory* — ``Settings`` is produced by an ``async def``
   factory (e.g. it awaits config I/O); the rest of the graph depends on it.

Only libraries with a real async resolution API are included (injex, dishka,
wireup, dependency-injector). punq and lagom have no async path.

Like the sync benchmark this is synthetic and graph-specific — a reproducible
sanity check for one shape, not a universal ranking.

Run from the repository root:

    uv run --with wireup --with dishka --with dependency-injector \
      python benchmarks/resolve_async.py
"""

from __future__ import annotations

import asyncio
import gc
import importlib.metadata as metadata
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Awaitable, Callable

import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from injex import Container as InjexContainer

import wireup
from dishka import Provider, Scope, from_context, make_async_container, provide
from wireup import injectable


class Settings:
    def __init__(self) -> None:
        self.database_url = "sqlite:///:memory:"


class ApiClient:
    def __init__(self, settings: Settings):
        self.settings = settings


class UserRepository:
    def __init__(self, client: ApiClient):
        self.client = client


class EmailSender:
    def __init__(self, client: ApiClient):
        self.client = client


class AuditLog:
    def __init__(self, settings: Settings):
        self.settings = settings


class RegisterUser:
    def __init__(self, repo: UserRepository, email: EmailSender, audit: AuditLog):
        self.repo = repo
        self.email = email
        self.audit = audit


settings = Settings()


async def make_settings() -> Settings:
    return settings


# wireup resolves string annotations against module globals (the file uses
# `from __future__ import annotations`), so its injectables live at module scope.
@injectable
class WSettings(Settings):
    pass


@injectable
class WApiClient:
    def __init__(self, settings: WSettings):
        self.settings = settings


@injectable(lifetime="transient")
class WRepo:
    def __init__(self, client: WApiClient):
        self.client = client


@injectable(lifetime="transient")
class WEmail:
    def __init__(self, client: WApiClient):
        self.client = client


@injectable(lifetime="transient")
class WAudit:
    def __init__(self, settings: WSettings):
        self.settings = settings


@injectable(lifetime="transient")
class WRegisterUser:
    def __init__(self, repo: WRepo, email: WEmail, audit: WAudit):
        self.repo, self.email, self.audit = repo, email, audit


@injectable
async def w_make_settings() -> Settings:
    return settings


@injectable
class WApiClient2:
    def __init__(self, settings: Settings):
        self.settings = settings


@injectable(lifetime="transient")
class WRepo2:
    def __init__(self, client: WApiClient2):
        self.client = client


@injectable(lifetime="transient")
class WEmail2:
    def __init__(self, client: WApiClient2):
        self.client = client


@injectable(lifetime="transient")
class WAudit2:
    def __init__(self, settings: Settings):
        self.settings = settings


@injectable(lifetime="transient")
class WRegisterUser2:
    def __init__(self, repo: WRepo2, email: WEmail2, audit: WAudit2):
        self.repo, self.email, self.audit = repo, email, audit


# --------------------------------------------------------------------------- #
# Scenario 1: synchronous graph resolved through the async API.
# --------------------------------------------------------------------------- #
def s1_injex() -> Callable[[], Awaitable[object]]:
    c = InjexContainer()
    c.add_instance(Settings, settings)
    c.add_singleton(ApiClient)
    c.add_transient(UserRepository)
    c.add_transient(EmailSender)
    c.add_transient(AuditLog)
    c.add_transient(RegisterUser)
    return lambda: c.aresolve(RegisterUser)


def s1_dishka() -> Callable[[], Awaitable[object]]:
    class P(Provider):
        s = from_context(provides=Settings, scope=Scope.APP)
        api = provide(ApiClient, scope=Scope.APP)
        repo = provide(UserRepository, scope=Scope.APP, cache=False)
        email = provide(EmailSender, scope=Scope.APP, cache=False)
        audit = provide(AuditLog, scope=Scope.APP, cache=False)
        ru = provide(RegisterUser, scope=Scope.APP, cache=False)

    container = make_async_container(P(), context={Settings: settings})
    return lambda: container.get(RegisterUser)


def s1_wireup() -> Callable[[], Awaitable[object]]:
    container = wireup.create_async_container(
        injectables=[WSettings, WApiClient, WRepo, WEmail, WAudit, WRegisterUser]
    )

    async def resolve() -> object:
        async with container.enter_scope() as scoped:
            return await scoped.get(WRegisterUser)

    return resolve


# --------------------------------------------------------------------------- #
# Scenario 2: Settings produced by an async factory.
# --------------------------------------------------------------------------- #
def s2_injex() -> Callable[[], Awaitable[object]]:
    c = InjexContainer()
    c.add_singleton_factory(Settings, make_settings)
    c.add_singleton(ApiClient)
    c.add_transient(UserRepository)
    c.add_transient(EmailSender)
    c.add_transient(AuditLog)
    c.add_transient(RegisterUser)
    return lambda: c.aresolve(RegisterUser)


def s2_dishka() -> Callable[[], Awaitable[object]]:
    class P(Provider):
        api = provide(ApiClient, scope=Scope.APP)
        repo = provide(UserRepository, scope=Scope.APP, cache=False)
        email = provide(EmailSender, scope=Scope.APP, cache=False)
        audit = provide(AuditLog, scope=Scope.APP, cache=False)
        ru = provide(RegisterUser, scope=Scope.APP, cache=False)

        @provide(scope=Scope.APP)
        async def s(self) -> Settings:
            return settings

    container = make_async_container(P())
    return lambda: container.get(RegisterUser)


def s2_wireup() -> Callable[[], Awaitable[object]]:
    container = wireup.create_async_container(
        injectables=[
            w_make_settings,
            WApiClient2,
            WRepo2,
            WEmail2,
            WAudit2,
            WRegisterUser2,
        ]
    )

    async def resolve() -> object:
        async with container.enter_scope() as scoped:
            return await scoped.get(WRegisterUser2)

    return resolve


async def bench(
    name: str,
    get: Callable[[], Awaitable[object]],
    *,
    iterations: int = 200_000,
    rounds: int = 9,
) -> tuple[str, float, float, float]:
    for _ in range(12_000):
        await get()

    samples = []
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(rounds):
            start = time.perf_counter_ns()
            for _ in range(iterations):
                obj = await get()
            end = time.perf_counter_ns()
            assert obj is not None
            samples.append((end - start) / iterations)
    finally:
        if gc_was_enabled:
            gc.enable()

    return name, statistics.median(samples), min(samples), max(samples)


def package_version(name: str) -> str:
    if name == "injex":
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text())
        return f"{data['project']['version']} (local checkout)"
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "unknown"


def report(title: str, results: list[tuple[str, float, float, float]]) -> None:
    print(f"\n{title}")
    print(f"{'library':<26} {'median µs/op':>14} {'min..max µs':>18}")
    for name, median, min_value, max_value in sorted(results, key=lambda r: r[1]):
        print(
            f"{name:<26} {median / 1000:>14.3f} "
            f"{min_value / 1000:>7.3f}..{max_value / 1000:<7.3f}"
        )


async def main() -> None:
    print(f"Python: {platform.python_version()} ({platform.machine()})")
    for package in ["injex", "wireup", "dishka"]:
        print(f"{package}: {package_version(package)}")

    s1 = [
        await bench("injex", s1_injex()),
        await bench("dishka", s1_dishka()),
        await bench("wireup scope/op", s1_wireup()),
    ]
    report("Scenario 1: synchronous graph via the async API", s1)

    s2 = [
        await bench("injex", s2_injex()),
        await bench("dishka", s2_dishka()),
        await bench("wireup scope/op", s2_wireup()),
    ]
    report("Scenario 2: graph with an async def factory (Settings)", s2)


if __name__ == "__main__":
    asyncio.run(main())
