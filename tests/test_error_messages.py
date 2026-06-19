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
