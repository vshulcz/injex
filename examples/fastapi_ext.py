"""FastAPI with the injex.ext.fastapi integration.

Run: pip install injex[fastapi] uvicorn; uvicorn examples.fastapi_ext:app
"""

from fastapi import FastAPI

from injex import Container
from injex.ext.fastapi import Provide, setup_injex


class Settings:
    def __init__(self) -> None:
        self.greeting = "hello"


class Greeter:
    def __init__(self, settings: Settings):
        self.settings = settings

    def greet(self, name: str) -> str:
        return f"{self.settings.greeting}, {name}"


def build_container() -> Container:
    container = Container()
    container.add_singleton(Settings)
    container.add_transient(Greeter)
    container.assert_valid()
    return container


app = FastAPI()
setup_injex(app, build_container())


@app.get("/greet/{name}")
def greet(name: str, greeter: Greeter = Provide(Greeter)) -> dict[str, str]:
    return {"message": greeter.greet(name)}
