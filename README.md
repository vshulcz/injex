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

use_case = container.resolve(RegisterUser)
user_id = use_case.execute("ada@example.com")
```

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
| Small API surface | ✅ | ❌ | ✅ | ✅ |

This table is not a benchmark. It shows the niche: Injex aims to be small and
explicit while still covering common application wiring needs.

## Documentation and examples

- [Tutorial](./docs/tutorial.md)
- [Clean architecture example](./examples/clean_architecture.py)
- [CLI application example](./examples/cli_app.py)
- [Testing overrides example](./examples/testing.py)
- [Scoped lifetime example](./examples/scoped.py)
- [Factories example](./examples/factory.py)
- [Named registrations example](./examples/named.py)

## Common use cases

- Service-layer wiring in web APIs without coupling code to a web framework.
- Clean architecture use cases with repositories, gateways, and presenters.
- CLI tools where commands share configuration, clients, and services.
- Background workers and consumers with per-job or per-message scopes.
- Unit tests that need explicit dependency replacement.

## Contributing

Contributions are welcome. Good first changes include documentation examples,
typing improvements, and small API refinements with tests.

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the local setup and contribution
guidelines.
