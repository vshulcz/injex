# API reference

This page lists the public API intended for application code.

## Container

```python
from injex import Container
```

### Registration

- `add_singleton(interface, implementation=None, name=None)`
- `add_transient(interface, implementation=None, name=None)`
- `add_scoped(interface, implementation=None, name=None)`
- `add_singleton_factory(interface, factory, name=None)`
- `add_transient_factory(interface, factory, name=None)`
- `add_scoped_factory(interface, factory, name=None)`
- `add_instance(interface, instance, name=None)`

If `implementation` is omitted, Injex uses `interface` as the concrete class.

### Resolving

- `resolve(interface, name=None)` returns one service instance.
- `resolve_all(interface, name=None)` returns all matching registrations.
- `create_scope()` creates a scope for scoped services. Usable as a context
  manager (`with container.create_scope() as scope:`).

To inject a named registration into a constructor, annotate the parameter:
`Annotated[T, Named("primary")]` (import `Named` from `injex`).

### Overrides

```python
with container.override(PaymentGateway, instance=fake_gateway):
    checkout = container.resolve(Checkout)
```

`override()` accepts one of `implementation`, `factory`, or `instance` and
restores the original registration when the context exits.

### Validation

- `validate()` returns a list of `ValidationError` objects.
- `assert_valid()` raises `ContainerValidationException` if validation fails.

## Scope

`Scope` has the same resolving methods as the root container:

- `resolve(interface, name=None)`
- `resolve_all(interface, name=None)`

Use a scope for request, message, job, or command lifetimes. A scope is meant to
be owned by one request/task — create one per request rather than sharing a
single scope across threads. The container itself is thread-safe to resolve from;
singletons are built once even under concurrent first resolves.

## Async

Async factories (`async def`) and async-generator resources are registered with
the same `add_*_factory` methods and resolved through the async API.

- `await container.aresolve(interface, name=None)` resolves one service, awaiting
  any async factory in the graph.
- `async with container.ascope() as scope:` opens an `AsyncScope`. Scoped and
  transient async resources resolved via `await scope.aresolve(...)` are finalized
  (LIFO) when the block exits.
- `await container.aclose()` finalizes singleton async resources at shutdown.

The synchronous `resolve()` raises `AsyncResolutionRequiredException` if the graph
needs async work. See [async resolution](./async.md) for the full guide.

## Exceptions

- `ServiceNotRegisteredException`
- `CyclicDependencyException`
- `MissingTypeAnnotationException`
- `InvalidLifestyleException`
- `ContainerValidationException`
- `AsyncResolutionRequiredException`
- `PropertyInjectionException`

All exception classes inherit from `DIException`.
