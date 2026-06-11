# Migrating from a factories module

Many Python applications start with a hand-written `factories.py` (or
`dependencies.py`) that builds the service graph. This guide shows how to move
that code to Injex without changing application classes.

The goal is not to replace factories everywhere. Keep manual factories when they
are still small and local. Move to Injex when the same graph is rebuilt in
several entrypoints (API startup, CLI commands, workers, tests) and drifts out of
sync.

## Before: manual factories

A typical factories module wires everything by hand and is imported by each
entrypoint:

```python
# factories.py
from functools import lru_cache

from .settings import Settings, load_settings
from .clients import ApiClient
from .repositories import UserRepository
from .services import EmailSender, RegisterUser


@lru_cache
def get_settings() -> Settings:
    return load_settings()


@lru_cache
def get_api_client() -> ApiClient:
    return ApiClient(get_settings())


def get_user_repository() -> UserRepository:
    return UserRepository(get_api_client())


def get_email_sender() -> EmailSender:
    return EmailSender(get_api_client())


def get_register_user() -> RegisterUser:
    return RegisterUser(get_user_repository(), get_email_sender())
```

This works, but it has known rough edges:

- lifetimes are encoded ad hoc (`lru_cache` for singletons, plain functions for
  per-call objects);
- there is no single place to validate that the graph is complete;
- tests patch module-level functions to swap a dependency;
- every new service adds another `get_*` function and another wiring line.

## After: one container at the composition root

The application classes stay exactly the same — plain constructors with type
hints. Only the wiring module changes:

```python
# composition.py
from injex import Container

from .settings import Settings, load_settings
from .clients import ApiClient
from .repositories import UserRepository
from .services import EmailSender, RegisterUser


def build_container() -> Container:
    container = Container()
    container.add_instance(Settings, load_settings())
    container.add_singleton(ApiClient)
    container.add_transient(UserRepository)
    container.add_transient(EmailSender)
    container.add_transient(RegisterUser)
    container.assert_valid()
    return container
```

Each entrypoint builds the container once and resolves what it needs:

```python
container = build_container()
register_user = container.resolve(RegisterUser)
```

## Mapping table

| Manual factory pattern | Injex registration |
| --- | --- |
| `@lru_cache def get_x() -> X: return X(...)` | `container.add_singleton(X)` |
| `def get_x() -> X: return X(...)` (new each call) | `container.add_transient(X)` |
| Per-request / per-job object reused within one unit | `container.add_scoped(X)` |
| `get_x()` returning a prebuilt object | `container.add_instance(X, obj)` |
| Factory with custom construction logic | `container.add_singleton_factory(X, factory)` / `add_transient_factory` |
| Two implementations of the same interface | `container.add_*(X, ImplA, name="a")` + `name="b"` |
| Constructor reads dependencies positionally | unchanged — Injex resolves them from type hints |

## What you stop writing by hand

- **Lifetime bookkeeping.** `add_singleton` / `add_transient` / `add_scoped`
  replace the `lru_cache`-or-not convention.
- **Wiring order.** You register services in any order; Injex resolves each
  constructor from its annotations.
- **Manual completeness checks.** `assert_valid()` reports missing
  registrations, missing annotations, and cycles before the first request or job
  — without constructing your services.

## Tests: from patching to overrides

Before, tests usually patched the factory module:

```python
def test_register(monkeypatch):
    monkeypatch.setattr(factories, "get_email_sender", lambda: FakeEmailSender())
    ...
```

After, production registrations stay untouched and the swap is scoped to a
`with` block:

```python
def test_register():
    container = build_container()
    fake = FakeEmailSender()
    with container.override(EmailSender, instance=fake):
        register_user = container.resolve(RegisterUser)
        register_user.execute("ada@example.com")
    assert fake.sent_to == ["ada@example.com"]
```

The override restores automatically when the block exits, so one test cannot leak
a fake into another.

## FastAPI, CLI, and workers reuse the same container

The composition root is framework-free, so each entrypoint adapts it at its edge:

```python
# FastAPI: build once in lifespan, expose via app.state
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.container = build_container()
    yield

def get_register_user(request: Request) -> RegisterUser:
    return request.app.state.container.resolve(RegisterUser)
```

```python
# Typer / worker / script: build once, resolve directly
container = build_container()
container.resolve(RegisterUser).execute("ada@example.com")
```

See [`fastapi-depends.md`](./fastapi-depends.md) for the HTTP-boundary rule and
[`examples/fastapi_lifespan.py`](../examples/fastapi_lifespan.py) for a complete
example.

## Incremental migration

You do not have to convert everything at once:

1. Add a container alongside the existing factories module.
2. Move the leaf services first (clients, repositories), keep `get_*` wrappers
   that call `container.resolve(...)` so callers do not change yet.
3. Move higher-level use cases once their dependencies are registered.
4. Replace test `monkeypatch` calls with `override()` as you touch each test.
5. Delete the old `get_*` functions when nothing imports them.

At any step the application classes themselves stay unchanged — only the wiring
moves.
