# Injex launch kit

Use these drafts when announcing Injex. Keep claims modest and technical.

## Short description

Injex is a tiny zero-dependency dependency injection container for Python
services, CLIs, workers, and clean architecture applications. It uses normal type
hints for constructor injection and includes scoped lifetimes, test overrides,
and dependency graph validation.

## GitHub / README tagline

Tiny typed dependency injection for Python apps that want explicit wiring without
a framework-sized container.

## LinkedIn draft

I released Injex, a small dependency injection container for Python applications.

It is meant for cases where manual wiring starts getting repetitive, but a large
provider-based container feels like too much. The API stays small: typed
constructor injection, singleton/transient/scoped lifetimes, factories,
temporary test overrides, and graph validation before startup.

The project is intentionally framework-agnostic, so the same service layer can be
used from web handlers, CLI commands, workers, and tests.

GitHub: https://github.com/vshulcz/injex
PyPI: https://pypi.org/project/injex/

## Reddit / Python community draft

I built Injex, a tiny zero-dependency DI container for Python.

The goal is not to replace every DI library. It is for smaller services, CLIs,
workers, and clean architecture code where you want typed constructor injection,
scoped lifetimes, test overrides, and startup validation without a provider DSL
or framework lock-in.

I would appreciate feedback on the API shape and docs:
https://github.com/vshulcz/injex

## Hacker News draft

Show HN: Injex — tiny typed dependency injection for Python

Injex is a small zero-dependency DI container for Python apps. It uses normal
type hints for constructor injection and supports scoped lifetimes, factories,
test overrides, and graph validation without constructing services.

I built it for service/CLI/worker code where manual wiring becomes repetitive,
but larger provider-based containers feel too heavy.

https://github.com/vshulcz/injex

## Telegram / short post

Released Injex: tiny typed DI for Python services, CLIs, and workers.

- zero runtime dependencies
- constructor injection from type hints
- singleton/transient/scoped lifetimes
- test overrides
- graph validation before startup

GitHub: https://github.com/vshulcz/injex
