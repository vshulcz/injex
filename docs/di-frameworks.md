# Compared to larger DI frameworks

Injex is intentionally small. It is not trying to replace every Python DI
framework.

Use Injex when you want:

- explicit registrations;
- constructor injection from type hints;
- singleton, transient, and scoped lifetimes;
- temporary test overrides;
- startup graph validation;
- zero runtime dependencies;
- low overhead for repeated resolves in small service graphs.

Use a larger DI framework when you want:

- a provider DSL as a first-class architecture tool;
- advanced configuration injection;
- framework integrations that own handler/task wiring;
- async resource orchestration built into the container;
- a broad ecosystem of container-specific features.

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

## Manual wiring

Manual wiring remains the best default for small apps. A few direct constructor
calls are clearer than any container.

Move to Injex when the same graph starts repeating across API startup, CLI
commands, workers, and tests.

## Benchmark context

In a small synthetic service graph, Injex resolves faster than several popular DI
containers on the project benchmark machine. Treat that as a sanity check, not a
universal ranking.

See the reproducible benchmark: [`benchmarks/resolve_graph.py`](../benchmarks/resolve_graph.py).
