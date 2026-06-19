# Tutorial

This walks through Injex feature by feature, starting from the smallest useful
container and adding things as you hit a reason for them. If you just want the
two-minute version, the [README](../README.md) quick start is enough; come back
here when you need factories, scopes, named registrations, or property injection.

For depth on a specific topic, each section links to its own guide.

## The core loop

You register classes against the container at startup, then resolve them. Injex
reads constructor type hints to figure out what to build.

```python
from injex import Container


class UserRepository:
    def save(self, email: str) -> int:
        return 42


class RegisterUser:
    def __init__(self, repo: UserRepository):
        self.repo = repo


container = Container()
container.add_transient(UserRepository)
container.add_transient(RegisterUser)

use_case = container.resolve(RegisterUser)  # UserRepository built and injected
```

`RegisterUser` never names `UserRepository` anywhere except its own constructor.
That is the whole point: classes declare what they need, the container decides
where instances come from.

## Lifetimes

A registration has a lifetime that controls how often the instance is rebuilt:

- `add_singleton` — built once, shared for the life of the container. Use it for
  configuration, connection pools, and clients.
- `add_transient` — a fresh instance on every resolve. Use it for use cases and
  anything that should not carry state between calls.
- `add_scoped` — one instance per scope (see [Scopes](#scopes) below). Use it for
  request- or job-owned objects like a database session.

```python
container.add_singleton(Settings)
container.add_transient(RegisterUser)
container.add_scoped(DbSession)
```

The second argument is the implementation, if it differs from the key:

```python
container.add_singleton(Cache, RedisCache)  # resolve(Cache) -> RedisCache
```

## Factories

When construction needs logic the constructor can't express — reading an env var,
building from a connection string — register a factory instead of a class. The
factory's own parameters are injected too.

```python
def make_pool(settings: Settings) -> ConnectionPool:
    return ConnectionPool(settings.database_url, size=5)


container.add_singleton_factory(ConnectionPool, make_pool)
```

There is a factory variant for each lifetime: `add_singleton_factory`,
`add_transient_factory`, `add_scoped_factory`. Async (`async def`) factories and
async-generator resources go through the async API — see [Async](./async.md).

### Resources with teardown

A **generator** factory is a resource: it yields the value and runs the code
after the `yield` as teardown. Scoped/transient resources are finalized when their
scope exits; singleton resources when `container.close()` is called (the container
is also a context manager).

```python
def db_session(settings: Settings):
    session = connect(settings.database_url)
    try:
        yield session
    finally:
        session.close()


container.add_scoped_factory(Session, db_session)

with container.create_scope() as scope:
    session = scope.resolve(Session)  # closed when the block exits
```

## Auto-registration

For larger apps, marking classes and registering them in one call beats a long
list of `add_*` lines. Decorate with `@injectable` and `scan` a module:

```python
from injex import Container, injectable


@injectable                          # transient by default
class UserRepository: ...


@injectable(lifestyle="singleton")
class ApiClient: ...


@injectable(provides=Notifier, name="email")
class EmailNotifier(Notifier): ...


import myapp.services
container = Container()
container.scan(myapp.services)        # registers the marked classes above
```

`scan` registers only classes *defined* in the module (not imported ones), and
nothing happens until you call it — `@injectable` is just a marker, so importing
a module never registers anything behind your back. You can also pass an explicit
list: `container.scan([UserRepository, ApiClient])`.

## Existing instances

If you already hold an object, register it directly. It is treated as a
singleton.

```python
container.add_instance(Settings, load_settings())
```

## Calling functions

`resolve` builds objects; `call` invokes a function, filling its annotated
parameters from the container. Pass the rest yourself — a request, parsed CLI
args, a queue message. This is how you keep handlers free of wiring without
turning them into classes.

```python
def register_user(email: str, use_case: RegisterUser) -> int:
    return use_case.execute(email)


container.call(register_user, email="ada@example.com")  # use_case is injected
```

`acall` is the async counterpart: it awaits async dependencies, awaits the
function if it's a coroutine, and finalizes any async resources opened for the
call when it returns.

For CLI commands, [`injex.ext.cli`](./recipes.md) wraps this up: mark the service
parameters with `Inject()` and decorate the command with `wire(container)`, and
Typer/Click only see the real CLI arguments.

```python
from injex.ext.cli import Inject, wire

@app.command()
@wire(container)
def greet(name: str, greeter: Greeter = Inject()):
    print(greeter.greet(name))
```

## Scopes

A scope is a boundary that scoped services live inside of — typically one web
request or one background job. Scoped services are shared within a scope and
rebuilt for the next one.

```python
container.add_scoped(DbSession)

with container.create_scope() as scope:
    a = scope.resolve(UnitOfWork)
    b = scope.resolve(UnitOfWork)
    assert a.session is b.session  # same DbSession within the scope
```

For the FastAPI wiring (container at startup, one scope per request) see
[Recipes](./recipes.md) and [`examples/fastapi_app.py`](../examples/fastapi_app.py).
For async resources that must be opened and closed around a request, see
[Async](./async.md).

## Resolving every implementation

Register the same key more than once and `resolve_all` returns all of them, in
registration order. This is how you build plugin lists, event handlers, or
middleware pipelines.

```python
container.add_transient(Notifier, EmailNotifier)
container.add_transient(Notifier, SmsNotifier)

for notifier in container.resolve_all(Notifier):
    notifier.send("hi")
```

More patterns: [Resolving multiple implementations](./resolve-all.md).

## Named registrations

When you need two implementations of the same type side by side, give them
names and resolve by name.

```python
container.add_singleton(Database, PrimaryDatabase, name="primary")
container.add_singleton(Database, ReplicaDatabase, name="replica")

replica = container.resolve(Database, name="replica")
```

To inject a specific one into a constructor, mark the parameter with
`Annotated[T, Named(...)]`:

```python
from typing import Annotated
from injex import Named


class ReportJob:
    def __init__(self, db: Annotated[Database, Named("replica")]):
        self.db = db  # gets ReplicaDatabase
```

## Optional dependencies

A parameter typed `X | None` (or with a default) resolves to `None` (or the
default) when nothing is registered for it, instead of raising.

```python
class DataService:
    def __init__(self, cache: Cache | None = None):
        self.cache = cache


container.add_transient(DataService)
container.resolve(DataService).cache  # None until a Cache is registered
```

## Property injection

Constructor injection covers most cases. When you can't change a constructor —
a framework base class, for example — declare the dependency as an `@inject`
method and read it as an attribute.

```python
from injex import inject


class Application:
    @inject
    def logger(self) -> Logger:
        ...

    def run(self) -> None:
        self.logger.info("starting")
```

Property injection falls off the compiled fast path, so prefer constructors when
you have the choice.

## Validation

`assert_valid()` checks the whole graph — missing registrations, missing
annotations, cycles — without constructing anything. Run it at startup or in a
test so wiring mistakes fail immediately instead of on the first request.

```python
container.assert_valid()
```

Use `validate()` if you want the list of problems to format yourself. Details and
the exact rules are in [Container validation](./validation.md).

## Overrides in tests

`override()` swaps a registration inside a `with` block and restores it on exit,
so a test can inject a fake without touching the production container.

```python
fake = FakePaymentGateway()
with container.override(PaymentGateway, instance=fake):
    container.resolve(Checkout).pay(1999)
assert fake.charges == [1999]
```

Existing scoped instances are not rewritten, so open scopes inside the override
block when a test exercises scoped services.

## Cycles

If two services depend on each other, resolving raises
`CyclicDependencyException` rather than recursing forever:

```python
class A:
    def __init__(self, b: "B"): ...


class B:
    def __init__(self, a: "A"): ...


container.add_transient(A)
container.add_transient(B)
container.resolve(A)  # CyclicDependencyException
```

`assert_valid()` reports the same cycle before you ever resolve.

## A larger example: a mediator

This ties the pieces together — `resolve_all` for the behavior pipeline, an
injected container, and a singleton composing transient behaviors around a
handler. A mediator decouples sending a request from handling it; behaviors add
cross-cutting concerns (logging, auth) without the handler knowing.

```python
from abc import ABC, abstractmethod
from typing import Callable

from injex import Container


class Request:
    def __init__(self, data: str):
        self.data = data


class Handler(ABC):
    @abstractmethod
    def handle(self, request: Request) -> str: ...


class Behavior(ABC):
    @abstractmethod
    def process(self, request: Request, call_next: Callable[[], str]) -> str: ...


class LoggingBehavior(Behavior):
    def process(self, request: Request, call_next: Callable[[], str]) -> str:
        print(f"log: {request.data}")
        return call_next()


class EchoHandler(Handler):
    def handle(self, request: Request) -> str:
        return f"processed: {request.data}"


class Mediator:
    def __init__(self, container):  # an unannotated `container` parameter is the container itself
        self.container = container

    def send(self, request: Request) -> str:
        handler = self.container.resolve(Handler)
        call = lambda: handler.handle(request)
        # Wrap each behavior around the handler; first registered runs outermost.
        for behavior in reversed(self.container.resolve_all(Behavior)):
            call = lambda b=behavior, nxt=call: b.process(request, nxt)
        return call()


container = Container()
container.add_transient(Behavior, LoggingBehavior)
container.add_transient(Handler, EchoHandler)
container.add_singleton(Mediator)

print(container.resolve(Mediator).send(Request("task")))
```

## Errors

Every Injex exception subclasses `DIException`, so you can catch the specific one
or all of them. The full list and when each is raised is in the
[API reference](./api.md#exceptions).

## Where to go next

- [Recipes](./recipes.md) — FastAPI, workers, CLIs, test boundaries.
- [Async](./async.md) — async factories and resource lifecycles.
- [Why Injex](./why-injex.md) — when to reach for it and when not to.
