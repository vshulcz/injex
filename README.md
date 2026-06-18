# Injex

[![Build](https://github.com/vshulcz/injex/actions/workflows/ci.yml/badge.svg)](https://github.com/vshulcz/injex/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/injex.svg)](https://pypi.org/project/injex/)
[![Downloads](https://static.pepy.tech/badge/injex/month)](https://pepy.tech/project/injex)
[![Coverage](https://codecov.io/gh/vshulcz/injex/branch/main/graph/badge.svg)](https://codecov.io/gh/vshulcz/injex)
[![Python](https://img.shields.io/badge/python-3.10%E2%80%933.14-blue)](https://pypi.org/project/injex/)
[![License](https://img.shields.io/github/license/vshulcz/injex.svg)](./LICENSE)

**Tiny typed dependency injection for Python that catches missing dependencies and
cycles _before_ your app starts — with zero runtime dependencies.**

You wire one service graph at startup, validate it in a single call, then reuse it
from FastAPI, Typer, workers, scripts, and tests. Application classes stay plain:
normal constructors, normal type hints, no decorators.

![Injex validates the dependency graph before startup](https://raw.githubusercontent.com/vshulcz/injex/main/site/assets/validate-demo.png)

```bash
pip install injex
```

## Quick start

```python
from injex import Container


class UserRepository:
    def save(self, email: str) -> int:
        return 42


class EmailSender:
    def send_welcome(self, email: str) -> None:
        print(f"Welcome, {email}")


class RegisterUser:
    def __init__(self, repo: UserRepository, email_sender: EmailSender):
        self.repo = repo
        self.email_sender = email_sender

    def execute(self, email: str) -> int:
        user_id = self.repo.save(email)
        self.email_sender.send_welcome(email)
        return user_id


container = Container()
container.add_singleton(UserRepository)
container.add_singleton(EmailSender)
container.add_transient(RegisterUser)

container.assert_valid()  # fail fast if the graph is incomplete

container.resolve(RegisterUser).execute("ada@example.com")
```

## What makes it different

Most small DI containers stop at "resolve a graph." Injex's distinctive feature is
that it can **check the whole graph without constructing anything**, so missing
registrations, missing annotations, and cycles surface at startup or in CI — not on
the first request or background job.

```python
errors = container.validate()       # list of problems, nothing constructed
container.assert_valid()            # or raise with all of them at once
```

That makes it safe to run as a startup guard even when real constructors open
sockets or files.

## Lifetimes, overrides, scopes

```python
container.add_singleton(ApiClient)     # one instance for the app lifetime
container.add_transient(UseCase)       # a new instance per resolve
container.add_scoped(RequestContext)   # one instance per scope (request/job)

# Swap a dependency inside a test, restored automatically on exit:
with container.override(EmailSender, instance=fake_sender):
    container.resolve(RegisterUser).execute("test@example.com")
```

See the [tutorial](./docs/tutorial.md) for factories, named registrations,
`resolve_all()`, optional dependencies, and property injection.

## When to use it

- A service layer reused by an API, CLI, worker, and tests, where copy-pasted
  wiring drifts out of sync.
- You want a missing or cyclic dependency to fail at startup, not at 3 AM.
- Tests should replace one real service with a fake without touching production
  wiring.

**When not to:** a handful of constructor calls in one entrypoint is clearer with
plain manual wiring — reach for Injex when that wiring starts repeating.

## Async

Injex resolves async dependencies too. Register an `async def` factory or an
async-generator resource and resolve it through `aresolve()` / `ascope()`:

```python
async def db_session(settings: Settings):  # async-generator resource
    pool = await open_pool(settings.database_url)
    try:
        yield pool
    finally:
        await pool.aclose()  # finalized when the scope exits

container.add_scoped_factory(Pool, db_session)

async with container.ascope() as scope:
    pool = await scope.aresolve(Pool)
```

Resources are finalized LIFO via the standard library's `AsyncExitStack` (still
zero runtime deps). The sync `resolve()` raises `AsyncResolutionRequiredException`
if the graph needs async work, so you never silently get an un-awaited object. See
[async resolution](./docs/async.md) and the
[FastAPI example](./examples/fastapi_async.py).

## Where it doesn't fit (yet)

- **No provider/config DSL.** If you want a rich configuration-injection system,
  `dependency-injector` is a better fit.
- **No deep framework auto-wiring.** Injex owns the graph; FastAPI/Typer adapt it at
  their edge — it won't inject into route signatures for you.

## Performance

Injex compiles and caches a flat creator per service graph. On a small synthetic
graph (singleton config + client, transient repository/service/use-case) it resolves
faster than several popular containers on the same machine:

| Library | Median resolve time |
| --- | ---: |
| manual wiring | `0.264 µs/op` |
| **Injex** | **`0.407 µs/op`** |
| dishka | `0.755 µs/op` |
| Wireup, same scope | `0.935 µs/op` |
| dependency-injector | `1.721 µs/op` |
| lagom | `10.010 µs/op` |
| punq | `58.786 µs/op` |

This is synthetic and graph-specific — **not** a universal ranking. Reproduce it:

```bash
uv run --with punq --with lagom --with dependency-injector --with wireup --with dishka \
  python benchmarks/resolve_graph.py
```

See [performance notes](./docs/performance.md) for the full table and method.

## How it fits

One validated graph at the composition root; every entrypoint resolves from it.

```mermaid
flowchart LR
  subgraph root["Composition root — one validated graph"]
    direction LR
    S[Settings] --> C[ApiClient]
    C --> R[UserRepository]
    C --> E[EmailSender]
    R --> U[RegisterUser]
    E --> U
  end
  root --> API[FastAPI]
  root --> CLI[Typer CLI]
  root --> WK[Worker]
  root --> TS[Tests]
```

## How it compares

| Feature | Injex | dependency-injector | punq | lagom |
| --- | ---: | ---: | ---: | ---: |
| Zero runtime dependencies | ✅ | ❌ | ✅ | ✅ |
| Type-hint constructor injection | ✅ | ✅ | ✅ | ✅ |
| Singleton / transient / scoped | ✅ | ✅ | partial | ✅ |
| Named registrations | ✅ | ✅ | ❌ | ✅ |
| Property injection | ✅ | ❌ | ❌ | ❌ |
| Temporary test overrides | ✅ | ✅ | ❌ | ✅ |
| **Graph validation without constructing services** | ✅ | ❌ | ❌ | ❌ |

For a deeper, fair comparison see [Injex vs other DI options](./docs/comparison.md).

## API at a glance

| Method | Use when |
| --- | --- |
| `add_singleton(T, Impl)` | One instance reused for the app lifetime. |
| `add_transient(T, Impl)` | A new instance on every resolve. |
| `add_scoped(T, Impl)` | One instance reused inside one scope. |
| `add_*_factory(T, factory)` | Construction needs custom code. |
| `add_instance(T, instance)` | You already have the object. |
| `resolve(T)` / `resolve_all(T)` | Resolve one, or all unnamed implementations. |
| `create_scope()` | Start a request, job, or message lifetime. |
| `override(T, ...)` | Temporarily replace a dependency in tests. |
| `validate()` / `assert_valid()` | Check wiring before startup. |

## Documentation

- [Docs site](https://vshulcz.github.io/injex/) · [Tutorial](./docs/tutorial.md) ·
  [API reference](./docs/api.md)
- [Validation guide](./docs/validation.md) ·
  [Comparison](./docs/comparison.md) ·
  [vs FastAPI Depends](./docs/fastapi-depends.md)
- [Recipes](./docs/recipes.md) ·
  [Migrating from a factories module](./docs/migrating-from-factories.md) ·
  [Performance](./docs/performance.md)
- Examples:
  [clean architecture](./examples/clean_architecture.py),
  [FastAPI lifespan](./examples/fastapi_lifespan.py),
  [CLI](./examples/cli_app.py),
  [testing](./examples/testing.py),
  [scopes](./examples/scoped.py)

## Contributing

Contributions are welcome when they keep the API small, tested, and dependency-free.
Useful changes usually improve documentation, typing, examples, or narrow edge cases.
See [CONTRIBUTING.md](./CONTRIBUTING.md).

Thanks to [Muhammad Saqib Atif](https://github.com/msaqibatifj),
[mahek](https://github.com/mahek56),
[oppnc](https://github.com/oppnc), and
[YuuGR1337](https://github.com/YuuGR1337) for improving Injex.
