# Injex docs

Start here when you want to wire a small Python application without pulling in a
framework-sized dependency injection container.

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
- [Usage scenarios](./usage-scenarios.md): where Injex fits in services, CLIs,
  workers, and tests.
- [Container validation](./validation.md): check wiring before startup without
  creating service instances.
- [API reference](./api.md): public methods, exceptions, and import surface.
- [Release process](./releasing.md): maintainer checklist for versioned releases.
- [Resolving multiple implementations](./resolve-all.md): use resolve_all() for handlers, plugins, and pipelines.

## Examples

- [Clean architecture](../examples/clean_architecture.py)
- [CLI application](../examples/cli_app.py)
- [FastAPI lifespan](../examples/fastapi_lifespan.py)
- [Testing overrides](../examples/testing.py)
- [Scoped services](../examples/scoped.py)
- [Factories](../examples/factory.py)
- [Named registrations](../examples/named.py)

## Project notes

- [Roadmap](../ROADMAP.md)
- [Contributing](../CONTRIBUTING.md)
- [Changelog](../CHANGELOG.md)
