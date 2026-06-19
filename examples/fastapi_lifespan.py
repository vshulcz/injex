"""FastAPI lifespan example with Injex as a framework-free composition root.

Optional example dependencies:

    pip install fastapi uvicorn

Run with:

    uvicorn examples.fastapi_lifespan:app --reload

The key boundary is:

- Injex builds the application service graph.
- FastAPI lifespan owns app startup and teardown.
- `Depends` only adapts `app.state` services to HTTP handlers.
- Application services import no FastAPI primitives.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from uuid import uuid4

from fastapi import Body, Depends, FastAPI, Request

from injex import Container


@dataclass(frozen=True)
class Settings:
    app_name: str = "Injex FastAPI lifespan example"


@dataclass(frozen=True)
class User:
    id: str
    email: str


class UserStore:
    def __init__(self):
        self._users: list[User] = []

    def add(self, user: User) -> None:
        self._users.append(user)

    def all(self) -> list[User]:
        return list(self._users)


class UserRepository:
    def __init__(self, store: UserStore):
        self.store = store

    def add_user(self, email: str) -> User:
        user = User(id=uuid4().hex, email=email)
        self.store.add(user)
        return user

    def list_users(self) -> list[User]:
        return self.store.all()


class RegisterUser:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def execute(self, email: str) -> User:
        return self.repository.add_user(email)


class ListUsers:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def execute(self) -> list[User]:
        return self.repository.list_users()


@dataclass(frozen=True)
class Services:
    container: Container

    @property
    def register_user(self) -> RegisterUser:
        return self.container.resolve(RegisterUser)

    @property
    def list_users(self) -> ListUsers:
        return self.container.resolve(ListUsers)


def build_services(settings: Settings) -> Services:
    container = Container()
    container.add_instance(Settings, settings)
    container.add_singleton(UserStore)
    container.add_transient(UserRepository)
    container.add_transient(RegisterUser)
    container.add_transient(ListUsers)
    container.assert_valid()
    return Services(container)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.services = build_services(Settings())
    yield


app = FastAPI(title="Injex FastAPI lifespan example", lifespan=lifespan)


def get_services(request: Request) -> Services:
    services = request.app.state.services
    assert isinstance(services, Services)
    return services


def get_register_user(services: Services = Depends(get_services)) -> RegisterUser:
    return services.register_user


def get_list_users(services: Services = Depends(get_services)) -> ListUsers:
    return services.list_users


@app.post("/users")
def create_user(
    email: str = Body(embed=True),
    use_case: RegisterUser = Depends(get_register_user),
):
    return asdict(use_case.execute(email))


@app.get("/users")
def list_users(use_case: ListUsers = Depends(get_list_users)):
    return [asdict(user) for user in use_case.execute()]


if __name__ == "__main__":
    services = build_services(Settings())
    user = services.register_user.execute("ada@example.com")
    print(asdict(user))
