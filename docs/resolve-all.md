# Resolving Multiple Implementations

Use `resolve_all()` when several implementations of the same interface
should all run — for example, notification handlers, pipeline steps, or plugins.

## Example: notification handlers

```python
from injex import Container

class Notifier:
    def notify(self, message: str) -> None: ...

class EmailNotifier:
    def notify(self, message: str) -> None:
        print(f"Email: {message}")

class SlackNotifier:
    def notify(self, message: str) -> None:
        print(f"Slack: {message}")

container = Container()
container.add_singleton(Notifier, EmailNotifier)
container.add_singleton(Notifier, SlackNotifier)

notifiers = container.resolve_all(Notifier)
for notifier in notifiers:
    notifier.notify("Deployment complete")
```

`resolve_all()` returns every registered implementation in registration order.
Use it when all handlers should run, not just one.

## When to use resolve_all()

- Fan-out notifications (email, Slack, SMS)
- Plugin systems where all plugins process an event
- Pipeline steps that all run in sequence