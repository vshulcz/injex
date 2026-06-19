import inspect
import unittest
from abc import abstractmethod

import injex
import injex.container as container_module
import injex.planning as planning
from injex import (
    Container,
    LifeStyle,
    ServiceNotRegisteredException,
    ValidationError,
    inject,
)


class TestCoverageEdges(unittest.TestCase):
    def test_validation_error_string_with_name_and_string_service(self):
        error = ValidationError("service", "primary", "broken")

        self.assertEqual(str(error), "service named 'primary': broken")

    def test_unhashable_callable_plan_fallback_handles_type_hints(self):
        class Dependency: ...

        class Factory:
            def __eq__(self, other):
                return isinstance(other, Factory)

            def __call__(self, dependency: Dependency, fallback: int = 1):
                return dependency, fallback

        plan = injex._get_callable_plan(Factory())

        self.assertEqual(len(plan.dependencies), 2)
        self.assertEqual(plan.dependencies[0].dependency_type, Dependency)
        self.assertTrue(plan.dependencies[1].has_default)

    def test_cached_injected_properties_finds_marked_methods(self):
        class Dependency: ...

        class Service:
            @inject
            @abstractmethod
            def dependency(self) -> Dependency: ...

        properties = injex._cached_injected_properties(Service)

        self.assertEqual(properties[0][0], "dependency")

    def test_fast_raw_creator_arities(self):
        class Target:
            def __init__(self, *values):
                self.values = values

        creators = [lambda scope, value=value: value for value in range(5)]

        self.assertEqual(injex._make_fast_raw_creator(Target, [])(None).values, ())
        self.assertEqual(
            injex._make_fast_raw_creator(Target, creators[:1])(None).values, (0,)
        )
        self.assertEqual(
            injex._make_fast_raw_creator(Target, creators[:2])(None).values, (0, 1)
        )
        self.assertEqual(
            injex._make_fast_raw_creator(Target, creators[:3])(None).values, (0, 1, 2)
        )
        self.assertEqual(
            injex._make_fast_raw_creator(Target, creators[:4])(None).values,
            (0, 1, 2, 3),
        )
        self.assertEqual(
            injex._make_fast_raw_creator(Target, creators[:5])(None).values,
            (0, 1, 2, 3, 4),
        )

    def test_validate_registration_error_branches(self):
        container = Container()
        key = ("service", None)

        errors = container._validate_registration(
            key,
            injex.Registration(kind=injex.RegistrationType.SERVICE),
            [],
        )
        self.assertIn("no implementation", errors[0].message)

        errors = container._validate_registration(
            key,
            injex.Registration(kind=injex.RegistrationType.FACTORY),
            [],
        )
        self.assertIn("Factory registration is empty", errors[0].message)

        errors = container._validate_registration(
            key,
            injex.Registration(kind="bad"),
            [],
        )
        self.assertIn("not supported", errors[0].message)

    def test_validate_class_reports_bad_property_hints_and_missing_return(self):
        container = Container()

        class MissingReturn:
            @inject
            @abstractmethod
            def dependency(self): ...

        errors = container._validate_class(MissingReturn, (MissingReturn, None), [])
        self.assertIn("no return type annotation", errors[0].message)

    def test_validate_callable_reports_inspection_failure_and_missing_annotation(self):
        container = Container()

        class BadSignature:
            @property
            def __signature__(self):
                raise ValueError("nope")

            def __call__(self): ...

        errors = container._validate_callable(BadSignature(), ("factory", None), [])
        self.assertIn("Cannot inspect dependencies", errors[0].message)

        def factory(missing): ...

        errors = container._validate_callable(factory, ("factory", None), [])
        self.assertIn("Missing type annotation", errors[0].message)

    def test_validation_key_resolves_string_annotation(self):
        container = Container()

        class Dependency: ...

        container.add_transient(Dependency)

        self.assertEqual(
            container._get_validation_key("Dependency"), (Dependency, None)
        )
        self.assertEqual(container._get_validation_key("missing"), ("missing", None))

    def test_fast_creator_branches_for_default_optional_instance_and_scoped(self):
        container = Container()

        class Missing: ...

        class OptionalConsumer:
            def __init__(self, missing: Missing | None = None):
                self.missing = missing

        class DefaultConsumer:
            def __init__(self, value: int = 42):
                self.value = value

        class ScopedService: ...

        class UsesScoped:
            def __init__(self, scoped: ScopedService):
                self.scoped = scoped

        container.add_transient(OptionalConsumer)
        container.add_transient(DefaultConsumer)
        container.add_scoped(ScopedService)
        container.add_transient(UsesScoped)
        container.add_instance(str, "instance")

        self.assertIsNone(container.resolve(OptionalConsumer).missing)
        self.assertEqual(container.resolve(DefaultConsumer).value, 42)
        self.assertEqual(container.resolve(str), "instance")

        scope = container.create_scope()
        first = scope.resolve(UsesScoped)
        second = scope.resolve(UsesScoped)
        self.assertIs(first.scoped, second.scoped)

    def test_fast_creator_falls_back_for_property_and_container_injection(self):
        container = Container()

        class Dependency: ...

        class PropertyService:
            @inject
            @abstractmethod
            def dependency(self) -> Dependency: ...

        class ContainerAware:
            def __init__(self, container):
                self.container = container

        container.add_transient(Dependency)
        container.add_transient(PropertyService)
        container.add_transient(ContainerAware)

        self.assertIsInstance(container.resolve(PropertyService).dependency, Dependency)
        self.assertIs(container.resolve(ContainerAware).container, container)

    def test_factory_lifestyles_and_errors(self):
        container = Container()

        class Service: ...

        container.add_singleton_factory(Service, Service)
        self.assertIs(container.resolve(Service), container.resolve(Service))

        class ScopedService: ...

        container.add_scoped_factory(ScopedService, ScopedService)
        scope = container.create_scope()
        self.assertIs(scope.resolve(ScopedService), scope.resolve(ScopedService))

        with self.assertRaises(ValueError):
            container._invoke_factory_registration(
                injex.Registration(kind=injex.RegistrationType.FACTORY),
                container.create_scope(),
            )

    def test_create_instance_error_branches(self):
        container = Container()
        scope = container.create_scope()

        with self.assertRaises(ValueError):
            container._create_instance_from_registration(
                injex.Registration(kind=injex.RegistrationType.SERVICE), scope
            )

        with self.assertRaises(ValueError):
            container._create_instance_from_registration(
                injex.Registration(kind=injex.RegistrationType.FACTORY), scope
            )

        with self.assertRaises(ValueError):
            container._create_instance_from_registration(
                injex.Registration(kind="bad"), scope
            )

    def test_resolve_errors_and_named_message(self):
        container = Container()

        with self.assertRaises(ServiceNotRegisteredException) as context:
            container.resolve("missing", name="primary")

        self.assertIn("with name 'primary'", str(context.exception))

    def test_unhashable_type_hint_fallback(self):
        class CallableObject:
            __annotations__ = {"return": int}

            def __eq__(self, other):
                return isinstance(other, CallableObject)

            def __call__(self) -> int:
                return 1

        self.assertEqual(injex._get_type_hints(CallableObject()), {"return": int})

    def test_cached_callable_plan_handles_type_hint_failure(self):
        def factory(value):
            return value

        original = planning._cached_type_hints

        def fail(func):
            raise RuntimeError("bad hints")

        try:
            planning._cached_type_hints = fail
            plan = planning._cached_callable_plan(factory)
        finally:
            planning._cached_type_hints = original

        self.assertEqual(plan.dependencies[0].dependency_type, inspect.Parameter.empty)

    def test_unhashable_callable_plan_fallback_unannotated_container_and_skip_self(
        self,
    ):
        class Factory:
            def __eq__(self, other):
                return isinstance(other, Factory)

            def __call__(self, container, missing):
                return container, missing

        plan = injex._get_callable_plan(Factory(), skip_self=True)

        self.assertTrue(plan.dependencies[0].inject_container)
        self.assertEqual(plan.dependencies[1].dependency_type, inspect.Parameter.empty)

    def test_validate_class_reports_property_type_hint_failure(self):
        container = Container()

        class Service:
            @inject
            @abstractmethod
            def dependency(self) -> int: ...

        original = container_module._cached_type_hints

        try:
            container_module._cached_type_hints = lambda func: (_ for _ in ()).throw(
                RuntimeError("bad property")
            )
            errors = container._validate_class(Service, (Service, None), [])
        finally:
            container_module._cached_type_hints = original

        self.assertIn("Cannot read type hints", errors[0].message)

    def test_validate_callable_type_hint_failure_uses_annotations(self):
        container = Container()

        def factory(value):
            return value

        original = container_module._get_type_hints
        try:
            container_module._get_type_hints = lambda func: (_ for _ in ()).throw(
                RuntimeError("bad hints")
            )
            errors = container._validate_callable(factory, ("factory", None), [])
        finally:
            container_module._get_type_hints = original

        self.assertIn("Missing type annotation", errors[0].message)

    def test_fast_creator_optional_without_default_and_missing_required(self):
        container = Container()

        class Missing: ...

        class OptionalConsumer:
            def __init__(self, missing: Missing | None):
                self.missing = missing

        class RequiredConsumer:
            def __init__(self, missing: Missing):
                self.missing = missing

        container.add_transient(OptionalConsumer)
        container.add_transient(RequiredConsumer)

        self.assertIsNone(container.resolve(OptionalConsumer).missing)
        with self.assertRaises(ServiceNotRegisteredException):
            container.resolve(RequiredConsumer)

    def test_dependency_plan_direct_error_and_cache_branches(self):
        container = Container()
        scope = container.create_scope()

        with self.assertRaises(ServiceNotRegisteredException):
            container._resolve_dependency_plan(
                injex._DependencyPlan(
                    name="dep",
                    dependency_type=object,
                    dependency_key=None,
                    has_default=False,
                    default=inspect.Parameter.empty,
                    is_optional=False,
                ),
                scope,
                object,
            )

        class Service: ...

        container.add_singleton(Service)
        plan = injex._DependencyPlan(
            name="service",
            dependency_type=Service,
            dependency_key=(Service, None),
            has_default=False,
            default=inspect.Parameter.empty,
            is_optional=False,
        )
        first = container._resolve_dependency_plan(plan, scope, object)
        second = container._resolve_dependency_plan(plan, scope, object)
        self.assertIs(first, second)

    def test_singleton_and_scoped_fallback_cache_branches(self):
        container = Container()
        scope = container.create_scope()

        class Service:
            @inject
            @abstractmethod
            def missing(self) -> str | None: ...

        singleton_registration = injex.Registration(
            kind=injex.RegistrationType.SERVICE,
            implementation=Service,
            lifestyle=LifeStyle.SINGLETON,
        )
        scoped_registration = injex.Registration(
            kind=injex.RegistrationType.SERVICE,
            implementation=Service,
            lifestyle=LifeStyle.SCOPED,
        )

        singleton_key = ("singleton", None)
        scoped_key = ("scoped", None)
        first = container._get_instance_from_registration(
            singleton_registration, scope, singleton_key
        )
        second = container._get_instance_from_registration(
            singleton_registration, scope, singleton_key
        )
        self.assertIs(first, second)

        first = container._get_instance_from_registration(
            scoped_registration, scope, scoped_key
        )
        second = container._get_instance_from_registration(
            scoped_registration, scope, scoped_key
        )
        self.assertIs(first, second)

    def test_convenience_factory_registration_methods(self):
        container = Container()

        class Singleton: ...

        class Transient: ...

        class Scoped: ...

        container.add_singleton_factory(Singleton, Singleton)
        container.add_transient_factory(Transient, Transient)
        container.add_scoped_factory(Scoped, Scoped)

        self.assertIs(container.resolve(Singleton), container.resolve(Singleton))
        self.assertIsNot(container.resolve(Transient), container.resolve(Transient))
        scope = container.create_scope()
        self.assertIs(scope.resolve(Scoped), scope.resolve(Scoped))


if __name__ == "__main__":
    unittest.main()
