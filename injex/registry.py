from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .planning import _FactoryPlan, _ServicePlan


class LifeStyle:
    TRANSIENT = "transient"
    SINGLETON = "singleton"
    SCOPED = "scoped"


class RegistrationType:
    SERVICE = "service"
    FACTORY = "factory"
    INSTANCE = "instance"


class Registration:
    __slots__ = (
        "kind",
        "implementation",
        "factory",
        "instance",
        "lifestyle",
        "plan",
        "fast_creator",
        "fast_creator_version",
        "fast_creator_needs_scope",
        "is_async",
        "is_resource",
    )

    def __init__(
        self,
        kind: str,  # registration type
        implementation: type | None = None,
        factory: Callable[..., Any] | None = None,
        instance: Any | None = None,
        lifestyle: str = LifeStyle.TRANSIENT,
    ):
        self.kind = kind
        self.implementation = implementation
        self.factory = factory
        self.instance = instance
        self.lifestyle = lifestyle
        self.plan: _ServicePlan | _FactoryPlan | None = None
        self.fast_creator: Callable[[Any], Any] | None = None
        self.fast_creator_version = -1
        self.fast_creator_needs_scope = False
        # Async support: a coroutine-function factory (is_async) or an
        # async-generator factory used as a resource with teardown (is_resource).
        # Both are resolved only through the async path; sync resolve rejects them.
        self.is_async = False
        self.is_resource = False


class OverrideContext:
    def __init__(
        self,
        container: Any,
        key: tuple[type | str, str | None],
        registration: Registration,
    ):
        self.container = container
        self.key = key
        self.registration = registration
        self._previous_registrations: list[Registration] | None = None
        self._previous_singletons: dict[Any, Any] = {}

    def __enter__(self) -> Any:
        self._previous_registrations = list(
            self.container._registrations.get(self.key, [])
        )
        self._previous_singletons = self.container._pop_singletons_for_key(self.key)
        self.container._registrations[self.key] = [self.registration]
        self.container._invalidate_fast_creators()
        return self.container

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.container._pop_singletons_for_key(self.key)
        if self._previous_registrations:
            self.container._registrations[self.key] = self._previous_registrations
        else:
            self.container._registrations.pop(self.key, None)
        self.container._singletons.update(self._previous_singletons)
        self.container._invalidate_fast_creators()
