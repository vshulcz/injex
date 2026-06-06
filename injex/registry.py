from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

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
    )

    def __init__(
        self,
        kind: str,  # registration type
        implementation: Optional[Type] = None,
        factory: Optional[Callable[..., Any]] = None,
        instance: Optional[Any] = None,
        lifestyle: str = LifeStyle.TRANSIENT,
    ):
        self.kind = kind
        self.implementation = implementation
        self.factory = factory
        self.instance = instance
        self.lifestyle = lifestyle
        self.plan: Optional[Union[_ServicePlan, _FactoryPlan]] = None
        self.fast_creator: Optional[Callable[[Any], Any]] = None
        self.fast_creator_version = -1
        self.fast_creator_needs_scope = False


class OverrideContext:
    def __init__(
        self,
        container: Any,
        key: Tuple[Union[Type, str], Optional[str]],
        registration: Registration,
    ):
        self.container = container
        self.key = key
        self.registration = registration
        self._previous_registrations: Optional[List[Registration]] = None
        self._previous_singletons: Dict[Any, Any] = {}

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
