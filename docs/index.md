# Injex docs

Start here when you want to wire a small Python application without pulling in a
framework-sized dependency injection container.

## What Injex does

- **Constructor injection** from plain type hints, with singleton / transient /
  scoped lifetimes, factories, named registrations, optional dependencies, and
  property injection — see the [tutorial](./tutorial.md).
- **Validation** of the whole graph before anything is constructed
  ([validation](./validation.md)).
- **Resources with teardown**, sync and async, finalized when their scope exits or
  on `close()` / `aclose()` ([async](./async.md)).
- **Function injection** — `call()` / `acall()` inject into any function
  ([tutorial](./tutorial.md#calling-functions)).
- **Auto-registration** — `@injectable` + `scan()`
  ([tutorial](./tutorial.md#auto-registration)).
- **Integrations** — [FastAPI](./fastapi-depends.md#optional-integration)
  (`injex.ext.fastapi`) and Typer/Click (`injex.ext.cli`).
- **Zero runtime dependencies**, typed (PEP 561), Python 3.10–3.14.

## Guides

- [Tutorial](./tutorial.md): registrations, lifetimes, factories, overrides, and
  common patterns.
- [Why Injex](./why-injex.md): positioning, trade-offs, and comparison with
  common alternatives.
- [Comparison guide](./comparison.md): when to choose Injex, manual wiring,
  framework dependencies, or a larger DI container.
- [Compared to FastAPI Depends](./fastapi-depends.md): keep `Depends` at the HTTP
  edge while sharing application wiring with workers and CLIs.
- [Compared to larger DI frameworks](./di-frameworks.md): choose between Injex,
  manual wiring, Wireup, Dishka, and dependency-injector.
- [Performance notes](./performance.md): benchmark shape, results, and how to
  reproduce the hot-path resolve comparison.
- [Recipes](./recipes.md): FastAPI composition root, worker job scope, CLI
  command wiring, and test override boundaries.
- [Migrating from a factories module](./migrating-from-factories.md): move a
  hand-written `factories.py` to Injex without changing application classes.
- [Async resolution](./async.md): async factories, async resources with
  scope/lifecycle finalization, and the FastAPI per-request pattern.
- [Container validation](./validation.md): check wiring before startup without
  creating service instances.
- [API reference](./api.md): public methods, exceptions, and import surface.
- [Release process](./releasing.md): maintainer checklist for versioned releases.
- [Resolving multiple implementations](./resolve-all.md): use resolve_all() for handlers, plugins, and pipelines.

## Examples

- [Clean architecture](../examples/clean_architecture.py)
- [Auto-registration with scan()](../examples/scan.py)
- [Factories](../examples/factory.py) ·
  [Resources with teardown](../examples/resources.py) ·
  [Scoped services](../examples/scoped.py)
- [Config injection](../examples/config_injection.py) ·
  [Testing overrides](../examples/testing.py)
- [FastAPI integration](../examples/fastapi_ext.py) ·
  [Async FastAPI](../examples/fastapi_async.py) ·
  [FastAPI lifespan](../examples/fastapi_lifespan.py)
- [CLI injection](../examples/cli_injection.py) ·
  [CLI application](../examples/cli_app.py)
- [Validation catches a cycle](../examples/cyclic.py) ·
  [Combined features](../examples/integration.py)

## Articles and launch notes

- [When Python manual wiring turns into copy-paste architecture](https://vshulcz.hashnode.dev/when-python-manual-wiring-turns-into-copy-paste-architecture)
- [Where should dependency wiring live in a Python app?](https://vshulcz.hashnode.dev/where-should-dependency-wiring-live-in-a-python-app)
- [Fast dependency injection in Python without a provider framework](https://dev.to/vshulcz/fast-dependency-injection-in-python-without-a-provider-framework-3dko)
- [Updates on X](https://x.com/vshulcz_dev)

## Project notes

- [Roadmap](../ROADMAP.md)
- [Contributing](../CONTRIBUTING.md)
- [Changelog](../CHANGELOG.md)
