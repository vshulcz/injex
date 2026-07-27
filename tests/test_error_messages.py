"""Resolution errors should read clearly and validate() shouldn't repeat itself."""

from injex import Container, ServiceNotRegisteredException


class DB:
    pass


class Repo:
    def __init__(self, db: DB):
        self.db = db


class RegisterUser:
    def __init__(self, repo: Repo):
        self.repo = repo


def test_missing_dependency_names_clean_type_and_requiring_site():
    c = Container()
    c.add_transient(Repo)  # DB not registered
    c.add_transient(RegisterUser)

    try:
        c.resolve(RegisterUser)
    except ServiceNotRegisteredException as exc:
        message = str(exc)
    else:
        raise AssertionError("expected ServiceNotRegisteredException")

    assert "'DB'" in message  # clean name, not "<class '...DB'>"
    assert "<class" not in message
    assert "Repo.db" in message  # points at who needed it


def test_top_level_missing_uses_clean_name():
    c = Container()
    try:
        c.resolve(DB)
    except ServiceNotRegisteredException as exc:
        assert "'DB'" in str(exc)
        assert "<class" not in str(exc)
    else:
        raise AssertionError("expected ServiceNotRegisteredException")


def test_validate_does_not_duplicate_shared_dependency_errors():
    # Two roots both depend on Repo, which depends on the unregistered DB.
    class OtherUser:
        def __init__(self, repo: Repo):
            self.repo = repo

    c = Container()
    c.add_transient(Repo)
    c.add_transient(RegisterUser)
    c.add_transient(OtherUser)

    errors = c.validate()
    messages = [str(e) for e in errors]
    assert len(messages) == len(set(messages))  # no duplicates


def test_validation_error_shows_full_resolution_path():
    class Session:
        pass

    class Store:
        def __init__(self, session: Session):
            self.session = session

    class UseCase:
        def __init__(self, store: Store):
            self.store = store

    class Handler:
        def __init__(self, use_case: UseCase):
            self.use_case = use_case

    c = Container()
    c.add_transient(Handler)
    c.add_transient(UseCase)
    c.add_transient(Store)  # Session never registered

    errors = c.validate()
    text = "\n".join(str(e) for e in errors)
    assert "Handler -> UseCase -> Store -> session" in text
    # the same missing binding reached by several routes is reported once
    assert sum("not registered: Session" in str(e) for e in errors) == 1


def test_validation_error_suggests_nearest_registered_name():
    class Database:
        pass

    class Databse:  # deliberate typo, registered instead of Database
        pass

    class Service:
        def __init__(self, db: Database):
            self.db = db

    c = Container()
    c.add_transient(Service)
    c.add_singleton(Databse)

    errors = c.validate()
    assert any("Did you mean Databse?" in str(e) for e in errors)
