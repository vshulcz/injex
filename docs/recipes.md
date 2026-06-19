# Recipes

These recipes show where to keep container calls in common application shapes.
They use small examples on purpose: the important part is the boundary, not the
domain model.

## FastAPI composition root

Keep the container at application startup. Request handlers should receive use
cases from FastAPI dependencies, not build repositories and clients themselves.

```python
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


def get_scope() -> Scope:
    return container.create_scope()


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
