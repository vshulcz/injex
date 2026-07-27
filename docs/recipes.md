# Recipes

These recipes show where to keep container calls in common application shapes.
They use small examples on purpose: the important part is the boundary, not the
domain model.

## One container, many entry points

The point of a container is that the *same* validated graph backs every way the
app runs — HTTP, a worker, a CLI, tests — so wiring never drifts between them.
Build it once, validate it once, resolve from it everywhere.

```python
# bootstrap.py — the one composition root
from injex import Container


def build_container() -> Container:
    container = Container()
    container.add_singleton(Settings)
    container.add_singleton(Database)
    container.add_scoped(UnitOfWork)
    container.add_transient(RegisterUser)
    container.assert_valid()  # fail fast, in every entry point and in CI
    return container
```

```python
# api.py
from injex.ext.fastapi import Provide, setup_injex

from bootstrap import build_container

app = FastAPI()
setup_injex(app, build_container())


@app.post("/users")
async def create(use_case: RegisterUser = Provide(RegisterUser)):
    return use_case.execute(...)
```

```python
# worker.py
from bootstrap import build_container

container = build_container()


def handle_job(payload) -> None:
    with container.create_scope() as scope:  # one scope per job
        scope.resolve(RegisterUser).execute(payload)
```

```python
# cli.py
from injex.ext.cli import Inject, wire

from bootstrap import build_container


@app.command()
@wire(build_container())
def register(email: str, use_case: RegisterUser = Inject()):
    use_case.execute(email)
```

Each entry point opens its own scope — a request, a job, a command — over one
shared graph. `python -m injex check bootstrap:build_container` validates that
graph in CI, so a dependency added for the API but forgotten in the worker fails
the build instead of a 3 a.m. page. The sections below show each entry point in
more detail.

## FastAPI composition root

Keep the container at application startup. Request handlers should receive use
cases from FastAPI dependencies, not build repositories and clients themselves.

```python
from collections.abc import Iterator

from fastapi import Depends, FastAPI

from injex import Container, Scope


class UserRepository:
    pass


class RegisterUser:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def execute(self) -> dict[str, str]:
        return {"status": "created"}


def build_container() -> Container:
    container = Container()
    container.add_scoped(UserRepository)
    container.add_transient(RegisterUser)
    container.assert_valid()
    return container


container = build_container()
app = FastAPI()


def get_scope() -> Iterator[Scope]:
    # `with` finalizes scoped resources (e.g. a DB session) when the request ends.
    with container.create_scope() as scope:
        yield scope


def get_register_user(scope: Scope = Depends(get_scope)) -> RegisterUser:
    return scope.resolve(RegisterUser)


@app.post("/users")
def create_user(use_case: RegisterUser = Depends(get_register_user)):
    return use_case.execute()
```

Use scoped registrations for request-owned objects, such as database sessions,
unit-of-work objects, request context, or per-request caches. Keep long-lived
clients as singletons.

The boilerplate above (the scope dependency and the per-service wrapper) is what
the optional `injex.ext.fastapi` integration writes for you — `setup_injex(app,
container)` plus `use_case: RegisterUser = Provide(RegisterUser)`. See
[Compared to FastAPI Depends](./fastapi-depends.md#optional-integration).

See also: [`examples/fastapi_app.py`](../examples/fastapi_app.py) and
[`examples/fastapi_ext.py`](../examples/fastapi_ext.py).

## One database session per request

Register the session as a scoped async-generator factory. Injex opens it the
first time it is resolved in a scope, hands the *same* session to everything in
that request, and finalizes it (LIFO, via the standard library's
`AsyncExitStack`) when the scope exits. No middleware, no contextvars.

```python
from collections.abc import AsyncIterator

from injex import Container


class Settings:
    dsn = "postgresql://localhost/app"


class Session:
    def __init__(self, dsn: str):
        self.dsn = dsn

    async def close(self) -> None: ...


class UserRepository:
    def __init__(self, session: Session):  # receives the request's session
        self.session = session


async def open_session(settings: Settings) -> AsyncIterator[Session]:
    session = Session(settings.dsn)
    try:
        yield session
    finally:
        await session.close()  # runs when the request scope exits


container = Container()
container.add_instance(Settings, Settings())
container.add_scoped_factory(Session, open_session)
container.add_transient(UserRepository)
container.assert_valid()


async def handle_request() -> None:
    async with container.ascope() as scope:
        repo_a = await scope.aresolve(UserRepository)
        repo_b = await scope.aresolve(UserRepository)
        assert repo_a.session is repo_b.session  # one session for the request
    # session.close() has run here; the next scope opens a fresh session
```

Under FastAPI the request scope is opened for you by `injex.ext.fastapi`, so a
route that asks for `UserRepository` (or the `Session` directly) gets one bound
to that request and released when it returns. Use `add_scoped_factory` with a
plain generator when the driver is synchronous — teardown works the same.

## Request data in the graph

Sometimes a factory needs the request itself: the authenticated user, a tenant
id, a trace id. Declare that type as context and pass it when you open the scope.
Injex injects it like any other dependency, and `validate()` still counts it as
satisfied — no globals, no `contextvars`.

```python
from injex import Container


class Request:
    def __init__(self, user_id: str):
        self.user_id = user_id


class AuditLog:
    def __init__(self, request: Request):  # needs the current request
        self.request = request


container = Container()
container.add_context(Request)  # supplied per scope, not constructed
container.add_transient(AuditLog)
container.assert_valid()  # Request counts as satisfied


def handle(request: Request) -> None:
    with container.create_scope(context={Request: request}) as scope:
        scope.resolve(AuditLog)  # gets this request
```

Resolving a context-dependent service without providing the value raises
`ContextValueMissingException`, so a forgotten `context=` fails loudly instead of
silently. Async is the same with `ascope(context={...})`.

## Worker job scope

Workers usually have two lifetimes: process lifetime and job lifetime. Keep
long-lived clients outside the job loop, then create a small job container and
one scope per job or message.

```python
from dataclasses import dataclass

from injex import Container


class QueueClient:
    pass


@dataclass
class JobContext:
    job_id: str


class JobScratchpad:
    pass


class ImportUserJob:
    def __init__(
        self,
        context: JobContext,
        queue: QueueClient,
        scratchpad: JobScratchpad,
    ):
        self.context = context
        self.queue = queue
        self.scratchpad = scratchpad

    def run(self) -> None:
        print(f"importing {self.context.job_id}")


queue_client = QueueClient()


def build_job_container(job_id: str) -> Container:
    container = Container()
    container.add_instance(QueueClient, queue_client)
    container.add_instance(JobContext, JobContext(job_id))
    container.add_scoped(JobScratchpad)
    container.add_transient(ImportUserJob)
    container.assert_valid()
    return container


def handle_job(job_id: str) -> None:
    container = build_job_container(job_id)
    scope = container.create_scope()
    scope.resolve(ImportUserJob).run()
```

The rule is simple: create a new scope for each job, and do not reuse scoped
state between jobs. If jobs run concurrently, avoid global overrides for
job-specific values; put those values in the per-job container or pass them as
method arguments.

## CLI command wiring

CLI modules are easy to turn into global state because commands often share
settings, API clients, repositories, and services. Keep command functions thin:
parse arguments, resolve a command object, run it.

```python
from dataclasses import dataclass

from injex import Container


@dataclass(frozen=True)
class Settings:
    api_url: str


class ApiClient:
    def __init__(self, settings: Settings):
        self.settings = settings


class SyncUsersCommand:
    def __init__(self, client: ApiClient):
        self.client = client

    def run(self) -> None:
        print(f"syncing through {self.client.settings.api_url}")


def build_container(settings: Settings) -> Container:
    container = Container()
    container.add_instance(Settings, settings)
    container.add_singleton(ApiClient)
    container.add_transient(SyncUsersCommand)
    container.assert_valid()
    return container


def main() -> None:
    settings = Settings(api_url="https://api.example.com")
    container = build_container(settings)
    container.resolve(SyncUsersCommand).run()
```

With Typer or Click, `injex.ext.cli` injects the command object so the framework
only sees real CLI arguments:

```python
from injex.ext.cli import Inject, wire


@app.command()
@wire(container)
def sync_users(command: SyncUsersCommand = Inject()) -> None:
    command.run()
```

See also: [`examples/cli_app.py`](../examples/cli_app.py) and
[`examples/cli_injection.py`](../examples/cli_injection.py).

## Test override boundary

Use overrides around the smallest block that needs the replacement. This keeps
test setup explicit and restores the original registration when the block exits.

```python
fake_client = FakeApiClient()

with container.override(ApiClient, instance=fake_client):
    command = container.resolve(SyncUsersCommand)
    command.run()
```

Avoid resolving services at import time. Build the container in a function, then
call that function from application startup, a CLI entrypoint, or a test fixture.
