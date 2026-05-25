# Container validation

Injex can validate the registered dependency graph before your application
starts. This catches common wiring mistakes early without constructing service
instances.

```python
from injex import Container


class Settings:
    pass


class ApiClient:
    def __init__(self, settings: Settings):
        self.settings = settings


container = Container()
container.add_singleton(Settings)
container.add_transient(ApiClient)

container.assert_valid()
```

## `validate()`

Use `validate()` when you want to decide how to report errors.

```python
errors = container.validate()

for error in errors:
    print(error)
```

Each item is a `ValidationError` with:

- `service`: the registered service being checked;
- `name`: the registration name, if any;
- `message`: a human-readable explanation.

## `assert_valid()`

Use `assert_valid()` for startup checks and tests. It raises
`ContainerValidationException` with all collected validation errors.

```python
def build_container() -> Container:
    container = Container()
    configure_services(container)
    container.assert_valid()
    return container
```

## What validation checks

- Missing constructor annotations.
- Missing factory parameter annotations.
- Missing registrations for required dependencies.
- Cyclic dependencies.
- Dependencies declared through `@inject` property methods.

Validation does not call constructors or factories. Runtime errors inside service
constructors still happen when the service is resolved.
