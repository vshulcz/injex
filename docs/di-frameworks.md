# Compared to larger DI frameworks

Injex is intentionally small. This page is about the named alternatives and where
Injex genuinely loses to them — for the general manual-vs-framework-vs-Injex
decision, see the [comparison guide](./comparison.md).

## Where Injex loses

Pick a larger framework when you need this — Injex deliberately doesn't do it:

- **A configuration/provider DSL.** Loading config from env/files, coercing types,
  and wiring values through provider objects is `dependency-injector`'s domain. In
  Injex configuration is a normal dependency: register a settings object, or values
  as named registrations and inject them with `Annotated[T, Named(...)]`.

Things people often assume Injex *can't* do, but it can: it manages async (and
sync) resource lifecycles via `ascope()` / `create_scope()`, injects into FastAPI
routes through [`injex.ext.fastapi`](./fastapi-depends.md), and injects into any
function (Typer/Click commands, workers) through `container.call()`.

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
