# Usage scenarios

These scenarios describe where Injex is meant to help. They are not claims about
production adoption.

## Service layer wiring

Use Injex as a composition root for repositories, gateways, clients, and use
cases. Application code can depend on normal Python types while startup code owns
the wiring.

Good fit when:

- constructors already describe dependencies clearly;
- several entrypoints share the same service graph;
- you want startup validation before serving traffic.

## CLI applications

CLI commands often share settings, API clients, repositories, and service
objects. A container keeps that setup in one place without turning modules into
global state.

Good fit when:

- commands reuse the same infrastructure;
- tests need fake clients or repositories;
- command handlers should stay small.

See: [`examples/cli_app.py`](../examples/cli_app.py).

## Background workers

Workers usually need long-lived clients and short-lived per-job state. Register
clients as singletons and create one scope per job or message for request-style
dependencies.

Good fit when:

- one job should reuse scoped state internally;
- different jobs should not share per-job objects;
- worker logic should be reusable in tests.

## Tests with external dependencies

Use `override()` to replace slow or external services with fakes only inside a
specific test block.

Good fit when:

- production registrations should remain unchanged;
- tests need explicit dependency replacement;
- you want overrides to restore automatically.

See: [`examples/testing.py`](../examples/testing.py).

## Startup validation

Use `validate()` or `assert_valid()` in startup checks and CI smoke tests to find
missing registrations, missing annotations, and cycles before objects are built.

Good fit when:

- constructors have side effects or connect to external systems;
- failing at startup is better than failing on first request;
- you want all wiring errors in one report.

See: [`docs/validation.md`](./validation.md).
