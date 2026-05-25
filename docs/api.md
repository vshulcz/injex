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
- `create_scope()` creates a scope for scoped services.

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

Use a scope for request, message, job, or command lifetimes.

## Exceptions

- `ServiceNotRegisteredException`
- `CyclicDependencyException`
- `MissingTypeAnnotationException`
- `InvalidLifestyleException`
- `ContainerValidationException`

All exception classes inherit from `DIException`.
