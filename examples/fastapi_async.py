"""FastAPI async example: per-request scope with an async resource.

Optional example dependencies:

    pip install fastapi uvicorn

Run with:

    uvicorn examples.fastapi_async:app --reload

The pattern:

- A singleton async resource (the connection pool) is opened once and closed by
  ``await container.aclose()`` at app shutdown.
- A scoped async resource (a per-request session) is opened when first resolved
  in a request and finalized when the request's scope exits.
- ``request_scope`` is a FastAPI dependency that opens one ``AsyncScope`` per
  request and closes it (and its resources) when the request finishes.
- Application services import no FastAPI primitives.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Request

from injex import AsyncScope, Container


# --- application layer (knows nothing about FastAPI or Injex) ---------------


class Pool:
    """A long-lived resource, e.g. a database connection pool."""

    def __init__(self) -> None:
        self.open = True

    async def acquire(self) -> str:
        return "connection"

    async def close(self) -> None:
        self.open = False


class Session:
    """A short-lived per-request resource built on the pool."""

    def __init__(self, pool: Pool) -> None:
        self.pool = pool
        self.closed = False

    async def fetch_user(self, uid: int) -> dict:
        await self.pool.acquire()
        return {"id": uid, "name": f"user-{uid}"}

    async def close(self) -> None:
        self.closed = True


class UserService:
    def __init__(self, session: Session) -> None:
        self.session = session

    async def get(self, uid: int) -> dict:
        return await self.session.fetch_user(uid)


# --- async resources (async generators -> opened + finalized) --------------


async def provide_pool() -> AsyncIterator[Pool]:
    pool = Pool()
    try:
        yield pool
    finally:
        await pool.close()


async def provide_session(pool: Pool) -> AsyncIterator[Session]:
    session = Session(pool)
    try:
        yield session
    finally:
        await session.close()


def build_container() -> Container:
    container = Container()
    container.add_singleton_factory(Pool, provide_pool)  # opened once, app-wide
    container.add_scoped_factory(Session, provide_session)  # one per request
    container.add_transient(UserService)
    container.assert_valid()
    return container


# --- FastAPI wiring ---------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.container = build_container()
    yield
    await app.state.container.aclose()  # closes the singleton pool


app = FastAPI(lifespan=lifespan)


async def request_scope(request: Request) -> AsyncIterator[AsyncScope]:
    async with request.app.state.container.ascope() as scope:
        yield scope  # the session opened here is closed when the request ends


async def get_user_service(
    scope: AsyncScope = Depends(request_scope),
) -> UserService:
    return await scope.aresolve(UserService)


@app.get("/users/{uid}")
async def read_user(
    uid: int, service: UserService = Depends(get_user_service)
) -> dict:
    return await service.get(uid)
