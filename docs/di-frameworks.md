# Compared to larger DI frameworks

Injex is intentionally small. This page is about the named alternatives and where
Injex genuinely loses to them — for the general manual-vs-framework-vs-Injex
decision, see the [comparison guide](./comparison.md).

## Where Injex loses

Pick a larger framework when you need any of these — Injex deliberately doesn't do
them:

- **Framework-native scopes for async resources.** Injex does open and close async
  resources (connection pools, `async def ... yield`) via `ascope()` / `aclose()`
  (see [async resolution](./async.md)). What the larger frameworks add on top is
  deeper integration with framework-managed request/session scopes — Dishka in
  particular wires its scopes directly into FastAPI/Litestar. With Injex you open
  the scope yourself at the request boundary.
- **A configuration/provider DSL.** If wiring config values through provider objects
  is part of your architecture, `dependency-injector` is purpose-built for it.
- **Deep framework auto-wiring.** Dishka/Wireup can plug directly into FastAPI or
  task-framework scopes and inject into handler signatures. Injex stays at the
  composition root and lets the framework adapt the graph at its edge.

## Dependency Injector

`dependency-injector` is mature and feature-rich. It is a strong fit when
provider objects, configuration providers, and explicit container classes are part
of the application architecture.

Injex is a better fit when the desired API is smaller: register normal classes,
validate the graph, resolve services, and keep constructors plain.

## Wireup and Dishka

Wireup and Dishka focus on modern autowiring and framework integration. They can
be a good choice when the container should participate directly in FastAPI or
task framework scopes.

Injex keeps the boundary more conservative: build the app graph at the
composition root, then let FastAPI/Typer/workers adapt that graph at their edge.

## Benchmark context

In a small synthetic service graph, Injex resolves faster than several popular DI
containers on the project benchmark machine. Treat that as a sanity check, not a
universal ranking.

See the reproducible benchmark: [`benchmarks/resolve_graph.py`](../benchmarks/resolve_graph.py).
