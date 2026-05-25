# Injex docs

Start here when you want to wire a small Python application without pulling in a
framework-sized dependency injection container.

## Guides

- [Tutorial](./tutorial.md): registrations, lifetimes, factories, overrides, and
  common patterns.
- [Why Injex](./why-injex.md): positioning, trade-offs, and comparison with
  common alternatives.
- [Usage scenarios](./usage-scenarios.md): where Injex fits in services, CLIs,
  workers, and tests.
- [Container validation](./validation.md): check wiring before startup without
  creating service instances.
- [API reference](./api.md): public methods, exceptions, and import surface.
- [Release process](./releasing.md): maintainer checklist for versioned releases.

## Examples

- [Clean architecture](../examples/clean_architecture.py)
- [CLI application](../examples/cli_app.py)
- [Testing overrides](../examples/testing.py)
- [Scoped services](../examples/scoped.py)
- [Factories](../examples/factory.py)
- [Named registrations](../examples/named.py)

## Project notes

- [Roadmap](../ROADMAP.md)
- [Contributing](../CONTRIBUTING.md)
- [Changelog](../CHANGELOG.md)
