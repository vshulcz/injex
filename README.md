# Injex

[![Build Status](https://github.com/vshulcz/injex/actions/workflows/ci.yml/badge.svg)](https://github.com/vshulcz/injex/actions/workflows/ci.yml)
[![pypi](https://img.shields.io/pypi/v/injex.svg)](https://pypi.python.org/pypi/injex)
[![Docs](https://img.shields.io/badge/docs-vshulcz.github.io%2Finjex-blue)](https://vshulcz.github.io/injex/)
[![Coverage](https://codecov.io/gh/vshulcz/injex/branch/main/graph/badge.svg)](https://codecov.io/gh/vshulcz/injex)
[![Python Versions](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12%20|%203.13-blue)](https://github.com/vshulcz/injex)
[![License](https://img.shields.io/github/license/vshulcz/injex.svg)](https://github.com/vshulcz/injex/blob/main/LICENSE)

Tiny typed dependency injection for Python apps that want explicit wiring without
a framework-sized container.

Injex keeps constructor injection boring: normal type hints, zero runtime
dependencies, scoped lifetimes, test overrides, and graph validation before your
app starts. It is designed for services, CLIs, workers, and clean architecture
code that should stay framework-agnostic.

```bash
pip install injex
```

Website: [vshulcz.github.io/injex](https://vshulcz.github.io/injex/)

## Use Injex when

- you have a service layer reused by an API, CLI, worker, and tests;
- constructors already describe dependencies with type hints;
- test doubles should replace external services without changing production wiring;
- startup should catch missing registrations before the first request or job.

## Skip Injex when

- a few manual constructor calls are still clear enough;
- your framework dependency system already covers every entrypoint;
- you need a large provider/configuration DSL.

## Why Injex?

- **Zero dependencies**: pure Python, easy to vendor, audit, and run anywhere.
- **Typed constructor injection**: dependencies are resolved from annotations.
- **Framework-agnostic**: use the same wiring in web apps, workers, CLIs, and
  tests.
- **Production lifetimes**: singleton, transient, and scoped services.
- **Factories and instances**: use custom creation logic or prebuilt objects.
- **Named registrations**: register multiple implementations of the same type.
- **Optional dependencies**: `Optional[T]` works without special configuration.
- **Test overrides**: swap real services for fakes in a small, explicit scope.
- **Container validation**: catch missing annotations, missing registrations, and
  dependency cycles before your app starts.

## Where it fits

Injex is useful when manual wiring starts to spread across your entrypoints, but
`providers`, global state, or a framework-specific container would be too much.

Common patterns:

- **Service layer**: wire repositories, gateways, clients, and use cases once at
  startup.
- **CLIs**: share configuration, API clients, and commands without module-level
  singletons.
- **Workers**: create one scope per job or message while reusing long-lived
  clients.
- **Tests**: override slow or external dependencies inside one `with` block.
- **Clean architecture**: keep application code depending on interfaces instead
  of framework-specific dependency hooks.

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

container.assert_valid()

use_case = container.resolve(RegisterUser)
user_id = use_case.execute("ada@example.com")
```

## Validate wiring before startup

`validate()` checks the registered dependency graph without constructing your
services. That makes it safe for startup checks and CI smoke tests.

```python
errors = container.validate()

if errors:
    for error in errors:
        print(error)
    raise SystemExit(1)
```

Use `assert_valid()` when you prefer a single exception with all validation
errors.

## Testing with overrides

Use `override()` to replace a dependency only inside a `with` block.

```python
class FakeEmailSender:
    def __init__(self):
        self.sent_to = []

    def send_welcome(self, email: str) -> None:
        self.sent_to.append(email)


fake_sender = FakeEmailSender()

with container.override(EmailSender, instance=fake_sender):
    use_case = container.resolve(RegisterUser)
    use_case.execute("test@example.com")

assert fake_sender.sent_to == ["test@example.com"]
```

## Scopes for request-style lifetimes

Scoped services are reused inside one scope and recreated for another scope.

```python
from injex import Container


class RequestContext:
    pass


container = Container()
container.add_scoped(RequestContext)

scope_a = container.create_scope()
scope_b = container.create_scope()

assert scope_a.resolve(RequestContext) is scope_a.resolve(RequestContext)
assert scope_a.resolve(RequestContext) is not scope_b.resolve(RequestContext)
```

## Feature comparison

| Feature | Injex | dependency-injector | punq | lagom |
| --- | ---: | ---: | ---: | ---: |
| Zero runtime dependencies | ✅ | ❌ | ✅ | ✅ |
| Type-hint constructor injection | ✅ | ✅ | ✅ | ✅ |
| Singleton / transient lifetimes | ✅ | ✅ | ✅ | ✅ |
| Scoped lifetime | ✅ | ✅ | ❌ | ✅ |
| Named registrations | ✅ | ✅ | ❌ | ✅ |
| Property injection | ✅ | ❌ | ❌ | ❌ |
| Temporary test overrides | ✅ | ✅ | ❌ | ✅ |
| Graph validation without object creation | ✅ | ❌ | ❌ | ❌ |
| Small API surface | ✅ | ❌ | ✅ | ✅ |

This table is not a benchmark. It shows the niche: Injex aims to be small and
explicit while still covering common application wiring needs.

## Documentation and examples

- [Docs site](https://vshulcz.github.io/injex/)
- [Docs index](./docs/index.md)
- [Tutorial](./docs/tutorial.md)
- [Validation guide](./docs/validation.md)
- [Why Injex](./docs/why-injex.md)
- [Comparison guide](./docs/comparison.md)
- [Usage scenarios](./docs/usage-scenarios.md)
- [API reference](./docs/api.md)
- [Article: When Python manual wiring turns into copy-paste architecture](https://vshulcz.hashnode.dev/when-python-manual-wiring-turns-into-copy-paste-architecture)
- [Clean architecture example](./examples/clean_architecture.py)
- [CLI application example](./examples/cli_app.py)
- [FastAPI application service example](./examples/fastapi_app.py)
- [Testing overrides example](./examples/testing.py)
- [Scoped lifetime example](./examples/scoped.py)
- [Factories example](./examples/factory.py)
- [Named registrations example](./examples/named.py)

## API at a glance

| Method | Use when |
| --- | --- |
| `add_singleton(T, Impl)` | One instance should be reused for the app lifetime. |
| `add_transient(T, Impl)` | A new instance should be created on every resolve. |
| `add_scoped(T, Impl)` | One instance should be reused inside one scope. |
| `add_*_factory(T, factory)` | Construction needs custom code. |
| `add_instance(T, instance)` | You already have the object to use. |
| `resolve(T)` | Resolve one service from the root container. |
| `resolve_all(T)` | Resolve all unnamed implementations for a type. |
| `create_scope()` | Start a request, job, or message lifetime. |
| `override(T, ...)` | Temporarily replace a dependency in tests. |
| `validate()` / `assert_valid()` | Check wiring before startup. |

## Common use cases

- Service-layer wiring in web APIs without coupling code to a web framework.
- Clean architecture use cases with repositories, gateways, and presenters.
- CLI tools where commands share configuration, clients, and services.
- Background workers and consumers with per-job or per-message scopes.
- Unit tests that need explicit dependency replacement.

## Contributors

Thanks to the people improving Injex through issues, reviews, and pull requests:

- [Muhammad Saqib Atif](https://github.com/msaqibatifj) — FastAPI example.
- [mahek](https://github.com/mahek56) — `resolve_all()` documentation recipe.
- [oppnc](https://github.com/oppnc) — nested override regression tests.
- [YuuGR1337](https://github.com/YuuGR1337) — README article link.

## Contributing

Contributions are welcome when they keep the API small, tested, and practical.
Useful changes usually improve documentation, typing, examples, or narrow edge
cases without adding runtime dependencies.

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the local setup and contribution
guidelines.
