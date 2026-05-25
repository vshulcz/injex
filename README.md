# Injex

[![Build Status](https://github.com/vshulcz/injex/actions/workflows/ci.yml/badge.svg)](https://github.com/vshulcz/injex/actions/workflows/ci.yml)
[![pypi](https://img.shields.io/pypi/v/injex.svg)](https://pypi.python.org/pypi/injex)
[![Coverage](https://codecov.io/gh/vshulcz/injex/branch/main/graph/badge.svg)](https://codecov.io/gh/vshulcz/injex)
[![Python Versions](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12%20|%203.13-blue)](https://github.com/vshulcz/injex)
[![License](https://img.shields.io/github/license/vshulcz/injex.svg)](https://github.com/vshulcz/injex/blob/main/LICENSE)

Tiny zero-dependency dependency injection container for Python services, CLIs,
workers, and clean architecture applications.

Injex is useful when hand-wiring dependencies starts to get noisy, but a large
framework-style container would be too much. It keeps the API small and uses
normal Python type hints for constructor injection.

```bash
pip install injex
```

## Why Injex?

- **Zero dependencies**: pure Python, easy to vendor, audit, and run anywhere.
- **Typed constructor injection**: dependencies are resolved from annotations.
- **Production lifetimes**: singleton, transient, and scoped services.
- **Factories and instances**: use custom creation logic or prebuilt objects.
- **Named registrations**: register multiple implementations of the same type.
- **Optional dependencies**: `Optional[T]` works without special configuration.
- **Test overrides**: swap real services for fakes in a small, explicit scope.
- **Container validation**: catch missing annotations, missing registrations, and
  dependency cycles before your app starts.

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

- [Docs index](./docs/index.md)
- [Tutorial](./docs/tutorial.md)
- [Validation guide](./docs/validation.md)
- [API reference](./docs/api.md)
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

## Contributing

Contributions are welcome when they keep the API small, tested, and practical.
Useful changes usually improve documentation, typing, examples, or narrow edge
cases without adding runtime dependencies.

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the local setup and contribution
guidelines.
