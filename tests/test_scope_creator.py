"""scope.resolve() runs a compiled scope-aware creator for graphs with scoped
services (instead of the interpreted walk). Behaviour must match: one scoped
instance per scope, shared across transitive deps, fresh in the next scope, and
transients still rebuilt."""

from injex import Container


class Settings:
    dsn = "x"


class ApiClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings


class Session:  # scoped: one per scope
    def __init__(self, client: ApiClient) -> None:
        self.client = client


class Repo:  # transient, depends on the scoped Session
    def __init__(self, session: Session) -> None:
        self.session = session


class UseCase:  # transient, depends on the transient Repo
    def __init__(self, repo: Repo) -> None:
        self.repo = repo


def _container() -> Container:
    c = Container()
    c.add_instance(Settings, Settings())
    c.add_singleton(ApiClient)
    c.add_scoped(Session)
    c.add_transient(Repo)
    c.add_transient(UseCase)
    c.assert_valid()
    return c


def test_scoped_instance_is_shared_within_a_scope():
    c = _container()
    with c.create_scope() as scope:
        a = scope.resolve(UseCase)
        b = scope.resolve(UseCase)
        # different transient use-cases and repos...
        assert a is not b
        assert a.repo is not b.repo
        # ...but the same scoped session underneath both
        assert a.repo.session is b.repo.session


def test_next_scope_gets_a_fresh_scoped_instance():
    c = _container()
    with c.create_scope() as first:
        s1 = first.resolve(UseCase).repo.session
    with c.create_scope() as second:
        s2 = second.resolve(UseCase).repo.session
    assert s1 is not s2


def test_singleton_shared_across_scopes():
    c = _container()
    with c.create_scope() as first:
        client1 = first.resolve(UseCase).repo.session.client
    with c.create_scope() as second:
        client2 = second.resolve(UseCase).repo.session.client
    assert client1 is client2  # singleton spans scopes
