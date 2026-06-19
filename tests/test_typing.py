"""Static typing contract for resolve().

``assert_type`` is a no-op at runtime but mypy (run on tests in CI) fails if the
inferred type drifts. This pins the overloads: ``resolve(Foo)`` returns ``Foo``,
not ``Any``, so downstream attribute access stays type-checked.
"""

from typing import TYPE_CHECKING, Any

from typing_extensions import assert_type

from injex import Container


class Foo:
    pass


def test_resolve_overloads_infer_concrete_types() -> None:
    c = Container()
    c.add_singleton(Foo)
    scope = c.create_scope()

    assert_type(c.resolve(Foo), Foo)
    assert_type(c.resolve_all(Foo), list[Foo])
    assert_type(scope.resolve(Foo), Foo)
    assert_type(scope.resolve_all(Foo), list[Foo])


if TYPE_CHECKING:
    # String interfaces have no static type to recover, so the overloads fall
    # back to Any. Checked by mypy; never executed (the names aren't registered).
    def _str_fallback_is_any(c: Container) -> None:
        scope = c.create_scope()
        assert_type(c.resolve("Foo"), Any)
        assert_type(scope.resolve("Foo"), Any)
