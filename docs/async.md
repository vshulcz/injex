# Async resolution

Injex is sync-first: the synchronous fast path is the default and stays as fast
as it is. Async support is a separate path you opt into when a dependency is
genuinely asynchronous — an `async def` factory, or a resource that must be
opened and closed around a request. It adds no third-party dependencies (it uses
the standard library's `contextlib.AsyncExitStack`).

## Async factories

Register a coroutine-function factory and resolve it through the async API. The
factory is awaited:

```python
from injex import Container


class Settings:
    pass


async def load_settings() -> Settings:
    # ... await config I/O ...
    return Settings()


container = Container()
container.add_singleton_factory(Settings, load_settings)


async def main() -> None:
    settings = await container.aresolve(Settings)
```

`aresolve` works anywhere you can `await`. The synchronous `resolve()` raises
`AsyncResolutionRequiredException` if the graph needs async work, so you never get
a half-built object:

```python
container.resolve(Settings)  # AsyncResolutionRequiredException
```

Async "infects" upward: a plain synchronous class that depends on an async
factory is also resolved through the async path.

## Async resources

A resource is something that must be **closed** after use — a database session, a
connection pool, an HTTP client. Declare it as an **async generator** factory:
the value you `yield` is injected, and the code after the `yield` runs when the
resource's scope ends.

```python
from typing import AsyncIterator


async def db_session(pool: Pool) -> AsyncIterator[Session]:
    session = Session(pool)
    try:
        yield session
    finally:
        await session.close()


container.add_scoped_factory(Session, db_session)
```

When the resource is finalized depends on its lifetime:

- **scoped / transient** — finalized when its `AsyncScope` exits;
- **singleton** — finalized by `await container.aclose()` at shutdown.

Finalization is LIFO, like nested `async with` blocks.

## Scopes

Open a scope with `async with`. Resources resolved inside are closed when the
block exits:

```python
async def handle_request() -> None:
    async with container.ascope() as scope:
        service = await scope.aresolve(RegisterUser)
        await service.execute("ada@example.com")
    # scoped/transient resources opened above are finalized here
```

Scoped resources are reused within one scope and recreated for the next, so a
scope maps naturally onto a request, job, or message.

`await container.aresolve(T)` is a convenience that opens a short-lived scope for
you. Because that scope closes on return, any scoped/transient *resource* opened
through it is finalized immediately — so for resources you want to keep open for
the duration of a request, resolve inside `async with container.ascope()`.
Singleton resources are unaffected: they live until `container.aclose()`.

## With FastAPI

Build the container in `lifespan`, open one scope per request as a dependency,
and close singleton resources at shutdown:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.container = build_container()
    yield
    await app.state.container.aclose()


async def request_scope(request: Request) -> AsyncIterator[AsyncScope]:
    async with request.app.state.container.ascope() as scope:
        yield scope


async def get_service(scope: AsyncScope = Depends(request_scope)) -> RegisterUser:
    return await scope.aresolve(RegisterUser)
```

A full runnable example is in
[`examples/fastapi_async.py`](../examples/fastapi_async.py).

## Notes

- The async path is interpreted (no compiled flat creator yet). Async resolution
  is dominated by `await` anyway, and keeping it separate means the synchronous
  fast path is completely unaffected.
- Cycle detection on the async path uses a per-resolution guard, so concurrent
  resolves on one container cannot interfere with each other.
- A singleton async resource is meant to live until `aclose()`. In tests, run the
  resolve and `aclose()` in the *same* event loop — `asyncio.run()` finalizes any
  suspended async generators when it shuts the loop down.
