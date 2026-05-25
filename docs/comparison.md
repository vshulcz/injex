# Comparison guide

This guide explains where Injex fits. It is not a benchmark.

## Quick decision table

| Need | Good fit |
| --- | --- |
| A few dependencies in one entrypoint | Manual wiring |
| Request handler dependencies inside one web framework | Framework dependency system |
| Shared service graph across API, CLI, worker, and tests | Injex |
| Typed constructor injection without a provider DSL | Injex |
| Temporary dependency replacement in tests | Injex |
| Graph validation before startup without building services | Injex |
| Complex provider/configuration framework | Larger DI container |

## Manual wiring

Manual wiring is the baseline. Start there when the graph is small and local.

Choose manual wiring when:

- dependencies are created in one file;
- tests can pass fakes directly;
- there is no repeated setup across entrypoints.

Consider Injex when the same wiring appears in app startup, CLI commands,
workers, and integration tests.

## Framework dependency systems

Framework dependency systems are good when all dependency resolution happens
inside that framework.

Choose framework dependencies when:

- handlers are the only entrypoint;
- lifecycle rules are framework-specific;
- service code does not need to run outside the framework.

Consider Injex when the same services also run from scripts, workers, scheduled
jobs, or tests.

## Larger DI containers

Larger containers can be the right choice for large applications with advanced
configuration needs.

Choose a larger container when:

- provider objects are part of the architecture;
- configuration injection is complex;
- built-in integrations are more important than a small API.

Choose Injex when the main needs are constructor injection, lifetimes, factories,
test overrides, named registrations, and validation.

## Why graph validation matters

Runtime dependency errors are expensive when they happen on the first real
request or background job. `Container.validate()` and `Container.assert_valid()`
check missing annotations, missing registrations, and cycles without constructing
services.

That makes validation safe for startup checks and CI smoke tests, even when real
constructors would open network connections or files.
