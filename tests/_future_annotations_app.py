"""Fixtures defined under ``from __future__ import annotations`` so every
annotation is a string that must be resolved at registration time."""

from __future__ import annotations


class Database: ...


class Repo:
    def __init__(self, db: Database) -> None:
        self.db = db


class Service:
    def __init__(self, repo: Repo) -> None:
        self.repo = repo


class Mailer: ...


class Handler:
    # 'Ghost' is never defined: get_type_hints() raises for the whole __init__,
    # which must NOT stop 'mailer' (a good, registered dependency) from
    # resolving, and must be reported the same way by validate() and resolve().
    def __init__(self, mailer: Mailer, ghost: Ghost) -> None:  # type: ignore[name-defined]  # noqa: F821
        self.mailer = mailer
