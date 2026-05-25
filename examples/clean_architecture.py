from dataclasses import dataclass
from typing import Protocol

from injex import Container


class UserRepository(Protocol):
    def create(self, email: str) -> int: ...


class NotificationGateway(Protocol):
    def send_welcome(self, email: str) -> None: ...


class InMemoryUserRepository:
    def __init__(self):
        self._users: list[str] = []

    def create(self, email: str) -> int:
        self._users.append(email)
        return len(self._users)


class ConsoleNotificationGateway:
    def send_welcome(self, email: str) -> None:
        print(f"Welcome email sent to {email}")


@dataclass(frozen=True)
class RegisterUserCommand:
    email: str


class RegisterUser:
    def __init__(self, users: UserRepository, notifications: NotificationGateway):
        self.users = users
        self.notifications = notifications

    def execute(self, command: RegisterUserCommand) -> int:
        user_id = self.users.create(command.email)
        self.notifications.send_welcome(command.email)
        return user_id


def build_container() -> Container:
    container = Container()
    container.add_singleton(UserRepository, InMemoryUserRepository)
    container.add_singleton(NotificationGateway, ConsoleNotificationGateway)
    container.add_transient(RegisterUser)
    return container


if __name__ == "__main__":
    app = build_container()
    use_case = app.resolve(RegisterUser)
    user_id = use_case.execute(RegisterUserCommand(email="ada@example.com"))
    print(f"Registered user #{user_id}")
