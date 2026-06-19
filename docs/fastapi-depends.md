# Compared to FastAPI Depends

FastAPI `Depends` is excellent at the HTTP boundary. It reads request data,
adapts framework objects, runs per-request dependencies, and keeps handlers
small.

Injex solves a different problem: application service wiring that must also run
outside HTTP.

## Use FastAPI Depends for

- request objects, headers, cookies, path/query/body parameters;
- authentication and authorization at the HTTP edge;
- short request-scoped adapters;
- exposing prebuilt services from `app.state` to handlers.

## Use plain factories or Injex for

- service graphs reused by FastAPI, Typer, workers, scripts, and tests;
- constructor-injected use cases, repositories, gateways, and clients;
- startup validation of missing registrations or dependency cycles;
- test overrides outside the HTTP layer.

## Recommended boundary

Keep the application graph framework-free:

```python
def build_services(settings: Settings) -> Services:
    container = Container()
    container.add_instance(Settings, settings)
    container.add_singleton(ApiClient)
    container.add_transient(UserRepository)
    container.add_transient(RegisterUser)
    container.assert_valid()
    return Services(container)
```

FastAPI adapts it in lifespan and dependencies:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.services = build_services(load_settings())
    yield


def get_register_user(request: Request) -> RegisterUser:
    return request.app.state.services.register_user
```

Workers and CLIs use the same builder directly:

```python
services = build_services(load_settings())
services.register_user.execute("ada@example.com")
```

The rule of thumb: FastAPI adapts HTTP; the application owns service wiring.

See also: [`examples/fastapi_lifespan.py`](../examples/fastapi_lifespan.py).

## FastAPI route example

Here is how to use the existing `get_register_user` dependency in a FastAPI route.

```python
from fastapi import APIRouter, Depends

router = APIRouter()

@router.post("/register")
def register_user(
    email: str,
    use_case: RegisterUser = Depends(get_register_user),
) -> int:
    return use_case.execute(email)
```

## Optional integration

If you'd rather not write the lifespan/scope glue yourself, the optional
`injex.ext.fastapi` integration (install with `pip install injex[fastapi]`) does
it for you: one Injex scope per request, resources finalized when the request
ends, and a `Provide` dependency.

```python
from injex.ext.fastapi import Provide, setup_injex

setup_injex(app, container)  # per-request scope + shutdown finalization

@app.post("/register")
def register_user(email: str, use_case: RegisterUser = Provide(RegisterUser)) -> int:
    return use_case.execute(email)
```

It's a thin adapter over `ascope()`; the container stays framework-agnostic, so
the same wiring still serves workers, CLIs, and tests. Full example:
[`examples/fastapi_ext.py`](../examples/fastapi_ext.py).
