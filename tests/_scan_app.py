"""Support module for test_scan: classes defined here for container.scan()."""

from injex import injectable

# An imported, already-marked class — scanning this module must NOT register it,
# because it isn't defined here.
from tests._scan_other import Foreign as Foreign


class Database:
    pass


@injectable
class Repository:
    def __init__(self, db: Database):
        self.db = db


@injectable(lifestyle="singleton")
class Cache:
    pass


class Port:
    pass


@injectable(provides=Port, name="primary")
class Adapter(Port):
    pass


class Unmarked:  # no decorator -> never registered
    pass
