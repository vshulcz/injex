"""container.scan(): auto-register @injectable classes."""

from injex import Container
from tests import _scan_app
from tests._scan_app import Adapter, Cache, Database, Port, Repository, Unmarked
from tests._scan_other import Foreign


def test_scan_module_registers_marked_classes_with_lifestyles():
    c = Container()
    c.add_singleton(Database)  # a plain dependency the marked Repository needs
    c.scan(_scan_app)

    assert isinstance(c.resolve(Repository), Repository)
    assert c.resolve(Repository) is not c.resolve(Repository)  # transient default
    assert c.resolve(Cache) is c.resolve(Cache)  # singleton


def test_scan_respects_provides_and_name():
    c = Container()
    c.scan(_scan_app)
    assert isinstance(c.resolve(Port, name="primary"), Adapter)


def test_scan_skips_unmarked_and_imported_classes():
    c = Container()
    c.scan(_scan_app)
    # Unmarked has no decorator; Foreign is imported, not defined in _scan_app.
    assert c._registrations.get((Unmarked, None)) is None
    assert c._registrations.get((Foreign, None)) is None


def test_scan_accepts_an_iterable_of_classes():
    c = Container()
    c.add_singleton(Database)
    c.scan([Repository, Cache])
    assert isinstance(c.resolve(Repository), Repository)


def test_scan_does_not_register_on_import():
    # Importing the module must not register anything by itself.
    fresh = Container()
    assert fresh._registrations == {}
