"""FastAPI example for using Injex as the application service container.

Optional example dependencies:

    pip install fastapi uvicorn

Run the app with:

    uvicorn examples.fastapi_app:app --reload

Each request creates a fresh Injex scope so scoped services, such as the
database session in this example, are reused within one request and recreated
for the next one.
"""

from dataclasses import asdict, dataclass, field
from uuid import uuid4

from fastapi import Body, Depends, FastAPI

from injex import Container, Scope


@dataclass(frozen=True)
class User:
    id: str
    email: str


@dataclass(frozen=True)
class DatabaseSession:
    session_id: str = field(default_factory=lambda: uuid4().hex)


class UserStore:
    def __init__(self):
        self._users: list[User] = []

    def add(self, user: User) -> None:
        self._users.append(user)

    def all(self) -> list[User]:
        return list(self._users)


class UserRepository:
    def __init__(self, store: UserStore, session: DatabaseSession):
        self.store = store
        self.session = session

    def add_user(self, email: str) -> User:
        user = User(id=uuid4().hex, email=email)
        self.store.add(user)
        return user

    def list_users(self) -> list[User]:
        return self.store.all()


class RegisterUser:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def execute(self, email: str) -> dict[str, object]:
        user = self.repository.add_user(email)
        return {"user": user, "session_id": self.repository.session.session_id}


class ListUsers:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def execute(self) -> dict[str, object]:
        return {
            "users": self.repository.list_users(),
            "session_id": self.repository.session.session_id,
        }


container = Container()
container.add_singleton(UserStore)
container.add_scoped(DatabaseSession)
container.add_transient(UserRepository)
container.add_transient(RegisterUser)
container.add_transient(ListUsers)

app = FastAPI(title="Injex FastAPI example")


def get_scope() -> Scope:
    return container.create_scope()


def get_register_user(scope: Scope = Depends(get_scope)) -> RegisterUser:
    return scope.resolve(RegisterUser)


def get_list_users(scope: Scope = Depends(get_scope)) -> ListUsers:
    return scope.resolve(ListUsers)


@app.post("/users")
def create_user(
    email: str = Body(embed=True),
    use_case: RegisterUser = Depends(get_register_user),
):
    result = use_case.execute(email)
    return {"user": asdict(result["user"]), "session_id": result["session_id"]}


@app.get("/users")
def list_users(use_case: ListUsers = Depends(get_list_users)):
    result = use_case.execute()
    return {
        "users": [asdict(user) for user in result["users"]],
        "session_id": result["session_id"],
    }


if __name__ == "__main__":
    scope = container.create_scope()
    register_user = scope.resolve(RegisterUser)
    print(register_user.execute("ada@example.com"))