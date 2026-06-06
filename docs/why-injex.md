# Why Injex

Python does not require a dependency injection container. Many small programs are
better with plain functions and manual wiring.

Injex is for the next step: applications where manual wiring starts leaking into
multiple entrypoints, tests need clean replacement of external dependencies, and
startup should fail early when the graph is incomplete.

## The niche

Injex is intentionally small:

- no runtime dependencies;
- no provider DSL;
- no required decorators for constructor injection;
- no framework lock-in;
- normal Python type hints as the wiring contract;
- cached resolution plans for fast repeated resolves.

The goal is not to replace every Python DI library. The goal is to cover the
boring 80% for services, CLIs, workers, and clean architecture applications.

## Compared with manual wiring

Manual wiring is often the best starting point. It is explicit and needs no
library.

It gets noisy when the same dependency graph appears in several places:

- web app startup;
- CLI commands;
- background workers;
- integration tests;
- local scripts.

Injex lets those entrypoints share one composition root while keeping the rest of
the application free from container calls.

## Compared with framework dependency systems

Framework dependency systems are good inside their framework. FastAPI `Depends`,
for example, is excellent for request handlers.

Injex is useful when the same application services also run outside the framework:

- CLI maintenance commands;
- batch jobs;
- message consumers;
- unit and integration tests;
- scripts that reuse the service layer.

The container stays independent from the transport layer.

## Compared with larger DI containers

Larger containers can provide advanced configuration systems, provider objects,
and integration packages. Injex avoids that on purpose.

Choose Injex when you want:

- a small API surface;
- typed constructor injection;
- scoped/singleton/transient lifetimes;
- temporary test overrides;
- dependency graph validation without constructing service instances.
- low overhead for the common path: singleton infrastructure plus transient
  application services.

Choose a larger container when you need a rich provider DSL, configuration
framework, or many built-in integrations.

## Design principle

Injex should stay boring in production: explicit registrations, predictable
lifetime rules, readable errors, and no hidden runtime dependencies.
