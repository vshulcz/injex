from __future__ import annotations

import gc
import importlib.metadata as metadata
import platform
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from injex import Container as InjexContainer

import punq
import wireup
from dependency_injector import containers, providers
from dishka import Provider, Scope, from_context, make_container, provide
from lagom import Container as LagomContainer
from wireup import injectable


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///:memory:"
    smtp_url: str = "smtp://localhost"


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
    def __init__(
        self,
        repo: UserRepository,
        email: EmailSender,
        audit: AuditLog,
    ):
        self.repo = repo
        self.email = email
        self.audit = audit


settings = Settings()
manual_client = ApiClient(settings)


def manual_resolve() -> RegisterUser:
    return RegisterUser(
        UserRepository(manual_client),
        EmailSender(manual_client),
        AuditLog(settings),
    )


def setup_injex() -> Callable[[], RegisterUser]:
    container = InjexContainer()
    container.add_instance(Settings, settings)
    container.add_singleton(ApiClient)
    container.add_transient(UserRepository)
    container.add_transient(EmailSender)
    container.add_transient(AuditLog)
    container.add_transient(RegisterUser)
    container.assert_valid()
    container.resolve(RegisterUser)
    return lambda: container.resolve(RegisterUser)


def setup_punq() -> Callable[[], RegisterUser]:
    container = punq.Container()
    container.register(Settings, instance=settings)
    container.register(ApiClient, ApiClient)
    container.register(UserRepository, UserRepository)
    container.register(EmailSender, EmailSender)
    container.register(AuditLog, AuditLog)
    container.register(RegisterUser, RegisterUser)
    container.resolve(RegisterUser)
    return lambda: container.resolve(RegisterUser)


def setup_lagom() -> Callable[[], RegisterUser]:
    container = LagomContainer()
    container[Settings] = settings
    container[ApiClient] = ApiClient
    container[UserRepository] = UserRepository
    container[EmailSender] = EmailSender
    container[AuditLog] = AuditLog
    container[RegisterUser] = RegisterUser
    container[RegisterUser]
    return lambda: container[RegisterUser]


class DishkaProvider(Provider):
    # Same graph: Settings is a provided instance, ApiClient a singleton
    # (cache=True), the rest transient (cache=False) so each get() builds anew.
    settings = from_context(provides=Settings, scope=Scope.APP)
    api_client = provide(ApiClient, scope=Scope.APP)
    repo = provide(UserRepository, scope=Scope.APP, cache=False)
    email = provide(EmailSender, scope=Scope.APP, cache=False)
    audit = provide(AuditLog, scope=Scope.APP, cache=False)
    register_user = provide(RegisterUser, scope=Scope.APP, cache=False)


def setup_dishka() -> Callable[[], RegisterUser]:
    container = make_container(DishkaProvider(), context={Settings: settings})
    container.get(RegisterUser)
    return lambda: container.get(RegisterUser)


class DIContainer(containers.DeclarativeContainer):
    settings_provider = providers.Object(settings)
    api_client = providers.Singleton(ApiClient, settings=settings_provider)
    repo = providers.Factory(UserRepository, client=api_client)
    email = providers.Factory(EmailSender, client=api_client)
    audit = providers.Factory(AuditLog, settings=settings_provider)
    register_user = providers.Factory(
        RegisterUser,
        repo=repo,
        email=email,
        audit=audit,
    )


def setup_dependency_injector() -> Callable[[], RegisterUser]:
    container = DIContainer()
    container.register_user()
    return lambda: container.register_user()


@injectable
class WSettings(Settings):
    pass


@injectable
class WApiClient:
    def __init__(self, settings: WSettings):
        self.settings = settings


@injectable(lifetime="transient")
class WUserRepository:
    def __init__(self, client: WApiClient):
        self.client = client


@injectable(lifetime="transient")
class WEmailSender:
    def __init__(self, client: WApiClient):
        self.client = client


@injectable(lifetime="transient")
class WAuditLog:
    def __init__(self, settings: WSettings):
        self.settings = settings


@injectable(lifetime="transient")
class WRegisterUser:
    def __init__(self, repo: WUserRepository, email: WEmailSender, audit: WAuditLog):
        self.repo = repo
        self.email = email
        self.audit = audit


def setup_wireup_scope_per_op() -> Callable[[], WRegisterUser]:
    container = wireup.create_sync_container(
        injectables=[
            WSettings,
            WApiClient,
            WUserRepository,
            WEmailSender,
            WAuditLog,
            WRegisterUser,
        ]
    )

    def resolve() -> WRegisterUser:
        with container.enter_scope() as scoped:
            return scoped.get(WRegisterUser)

    first = resolve()
    second = resolve()
    assert first is not second
    assert first.repo.client is second.repo.client
    return resolve


def setup_wireup_same_scope() -> Callable[[], WRegisterUser]:
    container = wireup.create_sync_container(
        injectables=[
            WSettings,
            WApiClient,
            WUserRepository,
            WEmailSender,
            WAuditLog,
            WRegisterUser,
        ]
    )
    scoped = container.enter_scope()
    scoped.__enter__()
    first = scoped.get(WRegisterUser)
    second = scoped.get(WRegisterUser)
    assert first is not second
    return lambda: scoped.get(WRegisterUser)


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


def package_version(name: str) -> str:
    if name == "injex":
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text())
        return f"{data['project']['version']} (local checkout)"
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "unknown"


def main() -> None:
    print(f"Python: {platform.python_version()} ({platform.machine()})")
    for package in [
        "injex",
        "wireup",
        "dishka",
        "dependency-injector",
        "lagom",
        "punq",
    ]:
        print(f"{package}: {package_version(package)}")

    cases = [
        ("manual", manual_resolve),
        ("injex", setup_injex()),
        ("wireup same scope", setup_wireup_same_scope()),
        ("wireup scope/op", setup_wireup_scope_per_op()),
        ("dishka", setup_dishka()),
        ("dependency-injector", setup_dependency_injector()),
        ("lagom", setup_lagom()),
        ("punq", setup_punq()),
    ]

    print("\nResolve benchmark")
    print("singleton Settings/ApiClient + transient Repo/Email/Audit/RegisterUser")
    results = [bench(name, fn) for name, fn in cases]
    baseline = dict((name, median) for name, median, _, _ in results)["manual"]

    print(f"{'library':<22} {'median µs/op':>14} {'x manual':>10} {'min..max µs':>18}")
    for name, median, min_value, max_value in sorted(results, key=lambda row: row[1]):
        print(
            f"{name:<22} {median / 1000:>14.3f} {median / baseline:>10.2f} "
            f"{min_value / 1000:>7.3f}..{max_value / 1000:<7.3f}"
        )


if __name__ == "__main__":
    main()
