# Injex Documentation

## Table of Contents

1. [Core Concepts](#core-concepts)
- [Service Registration](#service-registration)
    - [Sigleton services](#singleton-services)
    - [Transient services](#transient-services)
    - [Scoped services](#scoped-services)
- [Factory Registration](#factory-registration)
    - [Singleton Factories](#singleton-factories)
    - [Transient Factories](#transient-factories)
    - [Scoped Factories](#scoped-factories)
- [Instance Registration](#instances-registration)
- [Resolving Dependencies](#resolving-dependencies)
    - [Resolving Single Instances](#resolving-single-instances)
    - [Resolving Multiple Instances](#resolving-multiple-instances)
- [Property Injection](#property-injection)
- [Named Registrations](#named-registrations)
- [Optional Dependencies](#optional-dependencies)
- [Test Overrides](#test-overrides)
3. [Advanced Topics](#advanced-topics)
- [Scopes and Scoped Services](#scopes-and-scoped-services)
- [Cyclic Dependencies](#cyclic-dependencies)
- [Error Handling](#error-handling)
4. [Real-World Examples](#real-world-examples)
- [Building a Mediator with Pipeline Behaviors](#building-a-mediator-with-pipeline-behaviors)
- [Creating an API Service with Database Integration](#creating-an-api-service-with-database-integration)
5. [Best Practices](#best-practises)
6. [Conclusion](#conclusion)

## Core Concepts

### Service Registration

Registering services is the cornerstone of using Injex. You can register classes with different lifestyles.

#### Singleton Services
A singleton service is created once and reused throughout the application's lifetime.
```python
from injex import Container

class ConfigurationManager:
    pass

container = Container()
container.add_singleton(ConfigurationManager)

config1 = container.resolve(ConfigurationManager)
config2 = container.resolve(ConfigurationManager)
assert config1 is config2  # Same instance
```

#### Transient Services
A transient service creates a new instance every time it is resolved.
```python
class UserService:
    pass

container.add_transient(UserService)

user_service1 = container.resolve(UserService)
user_service2 = container.resolve(UserService)
assert user_service1 is not user_service2  # Different instances
```

#### Scoped Services
A scoped service is unique within a scope but shared within that scope.
```python
class RequestHandler:
    pass

container.add_scoped(RequestHandler)

scope1 = container.create_scope()
scope2 = container.create_scope()

handler1 = scope1.resolve(RequestHandler)
handler2 = scope1.resolve(RequestHandler)
handler3 = scope2.resolve(RequestHandler)

assert handler1 is handler2  # Same instance within scope1
assert handler1 is not handler3  # Different instances across scopes
```

### Factory Registration

Factories allow you to define custom logic for creating instances.

#### Singleton Factories
```python
def create_database_connection():
    return DatabaseConnection(pool_size=5)

container.add_singleton_factory(DatabaseConnection, create_database_connection)

db1 = container.resolve(DatabaseConnection)
db2 = container.resolve(DatabaseConnection)
assert db1 is db2  # Same instance
```

#### Transient Factories
```python
def create_user():
    return User(id=generate_unique_id())

container.add_transient_factory(User, create_user)

user1 = container.resolve(User)
user2 = container.resolve(User)
assert user1 is not user2  # Different instances
```

#### Scoped Factories
```python
def create_request_context():
    return RequestContext(request_id=generate_request_id())

container.add_scoped_factory(RequestContext, create_request_context)

scope = container.create_scope()
context1 = scope.resolve(RequestContext)
context2 = scope.resolve(RequestContext)
assert context1 is context2  # Same instance within scope
```

### Instance Registration

You can register an already created instance.
```python
config = ConfigurationManager()
container.add_instance(ConfigurationManager, config)

resolved_config = container.resolve(ConfigurationManager)
assert config is resolved_config  # Same instances
```

### Resolving Dependencies

#### Resolving Single Instances:
Retrieve an instance of a registered service.
```python
service = container.resolve(MyService)
```

#### Resolving Multiple Instances
If you have multiple implementations registered, you can resolve all of them.
```python
class NotificationService:
    pass

class EmailNotificationService(NotificationService):
    pass

class SMSNotificationService(NotificationService):
    pass

container.add_transient(NotificationService, EmailNotificationService)
container.add_transient(NotificationService, SMSNotificationService)

services = container.resolve_all(NotificationService)
for service in services:
    service.notify("Hello!")
```

### Property Injection

Use the @inject decorator to inject dependencies into properties.
```python
from injex import inject

class Logger:
    def log(self, message):
        print(message)

class Application:
    @inject
    def logger(self) -> Logger:
        pass

    def run(self):
        self.logger.log("Application is running.")

container.add_singleton(Logger)
container.add_transient(Application)

app = container.resolve(Application)
app.run()  # Output: Application is running.
```

### Named Registrations

Register multiple implementations under different names.
```python
class DatabaseService:
    pass

class MySQLDatabaseService(DatabaseService):
    pass

class PostgreSQLDatabaseService(DatabaseService):
    pass

container.add_singleton(DatabaseService, MySQLDatabaseService, name="mysql")
container.add_singleton(DatabaseService, PostgreSQLDatabaseService, name="postgresql")

mysql_service = container.resolve(DatabaseService, name="mysql")
postgresql_service = container.resolve(DatabaseService, name="postgresql")
```

### Optional Dependencies

Handle optional dependencies using Optional from the typing module.
```python
from typing import Optional

class CacheService:
    pass

class DataService:
    def __init__(self, cache: Optional[CacheService] = None):
        self.cache = cache

container.add_transient(DataService)

data_service = container.resolve(DataService)
assert data_service.cache is None  # CacheService was not registered
```

### Test Overrides

Use `override()` when a test needs a fake implementation without changing the
application container permanently.

```python
from injex import Container


class PaymentGateway:
    def charge(self, amount: int) -> str:
        return "real-payment-id"


class FakePaymentGateway:
    def __init__(self):
        self.charges = []

    def charge(self, amount: int) -> str:
        self.charges.append(amount)
        return "test-payment-id"


class Checkout:
    def __init__(self, payments: PaymentGateway):
        self.payments = payments

    def pay(self, amount: int) -> str:
        return self.payments.charge(amount)


container = Container()
container.add_singleton(PaymentGateway)
container.add_transient(Checkout)

fake_payments = FakePaymentGateway()

with container.override(PaymentGateway, instance=fake_payments):
    checkout = container.resolve(Checkout)
    assert checkout.pay(1999) == "test-payment-id"

assert fake_payments.charges == [1999]
```

The original registration is restored when the context exits. Existing scoped
instances are not rewritten, so create scopes inside the override block when the
test uses scoped services.

## Advanced Topics

### Scopes and Scoped Services
Scopes allow you to define a boundary within which scoped services are shared. This is particularly useful in web applications where you might want to share certain services within a single request but not across different requests.
```python
class RequestScopedService:
    pass

container.add_scoped(RequestScopedService)

# Simulating two different requests
scope1 = container.create_scope()
scope2 = container.create_scope()

service1 = scope1.resolve(RequestScopedService)
service2 = scope1.resolve(RequestScopedService)
service3 = scope2.resolve(RequestScopedService)

assert service1 is service2  # Same instance within scope1
assert service1 is not service3  # Different instances across scopes
```

### Cyclic Dependencies
Injex detects cyclic dependencies and raises a CyclicDependencyException to prevent infinite loops.
```python
class ServiceA:
    def __init__(self, service_b: "ServiceB"):
        self.service_b = service_b

class ServiceB:
    def __init__(self, service_a: "ServiceA"):
        self.service_a = service_a

container.add_transient(ServiceA)
container.add_transient(ServiceB)

try:
    container.resolve(ServiceA)
except CyclicDependencyException as e:
    print(f"Cyclic dependency detected: {e}")
```

### Error Handling

Injex provides specific exceptions to help you identify issues.

* `ServiceNotRegisteredException`: Thrown when trying to resolve an unregistered service.
* `CyclicDependencyException`: Thrown when a cyclic dependency is detected.
* `MissingTypeAnnotationException`: Thrown when a parameter lacks a type annotation.
* `InvalidLifestyleException`: Thrown when an invalid lifestyle is specified.

Example:
```python
try:
    container.resolve(UnregisteredService)
except ServiceNotRegisteredException as e:
    print(f"Service not registered: {e}")
```

## Real-World Examples

Building a Mediator with Pipeline Behaviors

A mediator pattern allows you to decouple the sending and handling of requests. Combining this with pipeline behaviors enables you to add cross-cutting concerns like logging, validation, and authorization.

```python
from abc import ABC, abstractmethod
from typing import Any, Callable, List

# Request interface
class IRequest(ABC):
    pass

# Handler interface
class IRequestHandler(ABC):
    @abstractmethod
    def handle(self, request: IRequest) -> Any:
        pass

# Pipeline behavior interface
class IPipelineBehavior(ABC):
    @abstractmethod
    def handle(self, request: IRequest, next: Callable) -> Any:
        pass

# Implement multiple behaviors
class LoggingBehavior(IPipelineBehavior):
    async def process(self, request: IRequest, next_handler: Callable) -> Any:
        print(f"Logging: {request}")
        return await next_handler()

class AuthorizationBehavior(IPipelineBehavior):
    async def process(self, request: IRequest, next_handler: Callable) -> Any:
        print("Authorizing request")
        # Perform authorization logic (e.g., check permissions)
        return await next_handler()

# Implement a Mediator
class Mediator:
    def __init__(self, container: Container):
        self.container = container

    def send(self, request: IRequest) -> Any:
        # Resolve all behaviors from the DI container
        behaviors = self.container.resolve_all(IPipelineBehavior)
        handler = self.container.resolve(IRequestHandler)

        return await self._execute_pipeline(request, handler)

    async def _execute_pipeline(
        self, request: IRequest, handler: IRequestHandler
    ) -> Any:
        behaviors: list[IPipelineBehavior] = self.container.resolve_all(
            IPipelineBehavior
        )

        async def final_handler() -> Any:  # type: ignore
            return await handler.handle(request)

        for behavior in reversed(behaviors):
            next_handler = final_handler

            def final_handler(beh=behavior, next_handler=next_handler):
                return beh.process(request=request, next_handler=next_handler)

        return await final_handler()

class MyRequest(IRequest):
    def __init__(self, data: str):
        self.data = data

class MyRequestHandler(IRequestHandler):
    def handle(self, request: MyRequest) -> Any:
        print(f"Processing request: {request.data}")
        return f"Processed: {request.data}"

# Create a DI container
container = Container()

# Register behaviors and handler
container.add_transient(IPipelineBehavior, LoggingBehavior)
container.add_transient(IPipelineBehavior, AuthorizationBehavior)
container.add_transient(IRequestHandler, MyRequestHandler)

# Register the mediator
container.add_singleton(Mediator)

import asyncio

async def main():
    # Resolve the mediator
    mediator = container.resolve(Mediator)

    # Send a request
    response = await mediator.send(MyRequest(data="Important Task"))
    print(response)

asyncio.run(main())


Output:
Logging: <__main__.MyRequest object at 0x...>
Authorizing request
Handling request: Important Task
Processed: Important Task
```

### Creating an API Service with Database Integration

Integrate Injex with a web framework like FastAPI to manage dependencies such as database connections and services.

```python
from fastapi import FastAPI, Depends
from injex import Container

app = FastAPI()
container = Container()

# Services
class DatabaseConnection:
    def __init__(self):
        self.connection = self.connect_to_db()

    def connect_to_db(self):
        # Database connection logic
        pass

class UserService:
    def __init__(self, db: DatabaseConnection):
        self.db = db

    def get_users(self):
        # Use self.db to fetch users
        return [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

# Configure DI
container.add_scoped(DatabaseConnection)
container.add_transient(UserService)

# Dependency Injection in FastAPI
def get_user_service() -> UserService:
    scope = container.create_scope()
    return scope.resolve(UserService)

@app.get("/users")
def list_users(service: UserService = Depends(get_user_service)):
    return service.get_users()
```
