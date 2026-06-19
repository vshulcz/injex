import unittest
from abc import ABC, abstractmethod

import injex
from injex import (
    Container,
    ContainerValidationException,
    CyclicDependencyException,
    DIException,
    InvalidLifestyleException,
    LifeStyle,
    MissingTypeAnnotationException,
    ServiceNotRegisteredException,
    ValidationError,
    inject,
)


class IServiceA:
    def do_something(self): ...


class ServiceA(IServiceA):
    def do_something(self):
        return "Service A is doing something."


class IServiceB:
    def do_something(self): ...


class ServiceB(IServiceB):
    def __init__(self, service_a: IServiceA):
        self.service_a = service_a

    def do_something(self):
        return f"Service B is doing something. {self.service_a.do_something()}"


class ServiceC:
    def __init__(self, service_d: "ServiceD"):
        self.service_d = service_d


class ServiceD:
    def __init__(self, service_c: ServiceC):
        self.service_c = service_c


class ServiceE:
    def __init__(self, missing_annotation):
        self.missing_annotation = missing_annotation


class ServiceA_cyclic:
    def __init__(self, service_b: "ServiceB_cyclic"):
        self.service_b = service_b


class ServiceB_cyclic:
    def __init__(self, service_c: "ServiceC_cyclic"):
        self.service_c = service_c


class ServiceC_cyclic:
    def __init__(self, service_a: ServiceA_cyclic):
        self.service_a = service_a


class ServiceA_prop_inj:
    @inject
    @abstractmethod
    def service_b(self) -> "ServiceB_prop_inj": ...


class ServiceB_prop_inj:
    @inject
    @abstractmethod
    def service_a(self) -> ServiceA_prop_inj: ...


class ServiceD_order:
    def __init__(self, service_e: "ServiceE_order"):
        self.service_e = service_e


class ServiceE_order:
    def __init__(self):
        self.value = "Service E"


class DependencyUnregistered(ABC):
    @abstractmethod
    def do_something(self): ...


class TestContainer(unittest.TestCase):
    def setUp(self):
        self.container = Container()

    def test_successful_resolution(self):
        self.container.register(IServiceA, ServiceA)
        self.container.register(IServiceB, ServiceB)
        service_b = self.container.resolve(IServiceB)
        result = service_b.do_something()
        expected = "Service B is doing something. Service A is doing something."
        self.assertEqual(result, expected)

    def test_service_not_registered_exception(self):
        with self.assertRaises(ServiceNotRegisteredException) as context:
            self.container.resolve("UnregisteredService")
        self.assertIn(
            "Service for interface 'UnregisteredService' is not registered.",
            str(context.exception),
        )

    def test_cyclic_dependency_exception(self):
        self.container.register(ServiceC)
        self.container.register(ServiceD)
        with self.assertRaises(CyclicDependencyException) as context:
            self.container.resolve(ServiceC)
        self.assertIn("Cyclic dependency detected", str(context.exception))

    def test_missing_type_annotation_exception(self):
        self.container.register(ServiceE)
        with self.assertRaises(MissingTypeAnnotationException) as context:
            self.container.resolve(ServiceE)
        self.assertIn(
            "Missing type annotation for parameter 'missing_annotation' "
            "in class 'ServiceE'.",
            str(context.exception),
        )

    def test_singleton_lifestyle(self):
        self.container.register(IServiceA, ServiceA, lifestyle=LifeStyle.SINGLETON)
        service_a1 = self.container.resolve(IServiceA)
        service_a2 = self.container.resolve(IServiceA)
        self.assertIs(service_a1, service_a2)

    def test_transient_lifestyle(self):
        self.container.register(IServiceA, ServiceA, lifestyle=LifeStyle.TRANSIENT)
        service_a1 = self.container.resolve(IServiceA)
        service_a2 = self.container.resolve(IServiceA)
        self.assertIsNot(service_a1, service_a2)

    def test_invalid_lifestyle_exception(self):
        with self.assertRaises(InvalidLifestyleException) as context:
            self.container.register(IServiceA, ServiceA, lifestyle="invalid")
        self.assertIn("Invalid lifestyle 'invalid'.", str(context.exception))

    def test_service_with_no_dependencies(self):
        class SimpleService:
            def do_something(self):
                return "SimpleService is doing something."

        self.container.register(SimpleService)
        service = self.container.resolve(SimpleService)
        result = service.do_something()
        self.assertEqual(result, "SimpleService is doing something.")

    def test_named_registrations(self):
        class ILogger(ABC):
            @abstractmethod
            def log(self, message: str): ...

        class ConsoleLogger(ILogger):
            def log(self, message: str):
                return f"Console Logger: {message}"

        class FileLogger(ILogger):
            def log(self, message: str):
                return f"File Logger: {message}"

        self.container.register(ILogger, ConsoleLogger, name="console")
        self.container.register(ILogger, FileLogger, name="file")

        console_logger = self.container.resolve(ILogger, name="console")
        file_logger = self.container.resolve(ILogger, name="file")

        self.assertIsInstance(console_logger, ConsoleLogger)
        self.assertIsInstance(file_logger, FileLogger)
        self.assertNotEqual(console_logger.log("Test"), file_logger.log("Test"))

    def test_factory_registration(self):
        class IService(ABC):
            @abstractmethod
            def do_work(self): ...

        class Service(IService):
            def __init__(self, value: int):
                self.value = value

            def do_work(self):
                return f"Value is {self.value}"

        def factory():
            return Service(42)

        self.container.register_factory(IService, factory)

        service = self.container.resolve(IService)
        result = service.do_work()
        self.assertEqual(result, "Value is 42")

    def test_optional_dependencies(self):
        class IOptionalService(ABC):
            @abstractmethod
            def do_something(self): ...

        class OptionalService(IOptionalService):
            def do_something(self):
                return "Optional service is doing something."

        class MainService:
            def __init__(self, optional_service: IOptionalService | None = None):
                self.optional_service = optional_service

            def perform_action(self):
                if self.optional_service:
                    return self.optional_service.do_something()
                else:
                    return "Optional service is not available."

        self.container.register(MainService)

        main_service = self.container.resolve(MainService)
        result = main_service.perform_action()
        self.assertEqual(result, "Optional service is not available.")

        self.container.register(IOptionalService, OptionalService)

        main_service_with_optional = self.container.resolve(MainService)
        result = main_service_with_optional.perform_action()
        self.assertEqual(result, "Optional service is doing something.")

    def test_property_injection(self):
        class DependencyA:
            def work(self):
                return "Dependency A is working."

        class DependencyB:
            def work(self):
                return "Dependency B is working."

        class ServiceWithPropertyInjection:
            @inject
            @abstractmethod
            def dependency_a(self) -> DependencyA: ...

            @inject
            @abstractmethod
            def dependency_b(self) -> DependencyB: ...

            def perform_action(self):
                return f"{self.dependency_a.work()} and {self.dependency_b.work()}"

        self.container.register(DependencyA)
        self.container.register(DependencyB)
        self.container.register(ServiceWithPropertyInjection)

        service = self.container.resolve(ServiceWithPropertyInjection)
        result = service.perform_action()
        expected = "Dependency A is working. and Dependency B is working."
        self.assertEqual(result, expected)

    def test_scoped_lifecycle(self):
        class IService(ABC):
            @abstractmethod
            def get_id(self): ...

        class Service(IService):
            def __init__(self):
                self.id = id(self)

            def get_id(self):
                return self.id

        self.container.register(IService, Service, lifestyle=LifeStyle.SCOPED)

        scope1 = self.container.create_scope()
        service1_a = scope1.resolve(IService)
        service1_b = scope1.resolve(IService)
        self.assertIs(service1_a, service1_b)

        scope2 = self.container.create_scope()
        service2_a = scope2.resolve(IService)
        self.assertIsNot(service1_a, service2_a)

    def test_multiple_implementations(self):
        class IService(ABC):
            @abstractmethod
            def process(self): ...

        class ImplOne(IService):
            def process(self):
                return "Implementation One"

        class ImplTwo(IService):
            def process(self):
                return "Implementation Two"

        self.container.register(IService, ImplOne, name="one")
        self.container.register(IService, ImplTwo, name="two")

        service_one = self.container.resolve(IService, name="one")
        service_two = self.container.resolve(IService, name="two")

        self.assertEqual(service_one.process(), "Implementation One")
        self.assertEqual(service_two.process(), "Implementation Two")

    def test_unregistered_optional_dependency(self):
        class IService(ABC): ...

        class ConsumerService:
            def __init__(self, service: IService | None = None):
                self.service = service

        self.container.register(ConsumerService)

        consumer = self.container.resolve(ConsumerService)
        self.assertIsNone(consumer.service)

    def test_complex_cyclic_dependency(self):
        self.container.register(ServiceA_cyclic)
        self.container.register(ServiceB_cyclic)
        self.container.register(ServiceC_cyclic)

        with self.assertRaises(CyclicDependencyException) as context:
            self.container.resolve(ServiceA_cyclic)
        self.assertIn("Cyclic dependency detected", str(context.exception))

    def test_singleton_and_scoped_lifecycles(self):
        class IServiceSingleton:
            def __init__(self):
                self.id = id(self)

        class IServiceScoped:
            def __init__(self):
                self.id = id(self)

        class ConsumerService:
            def __init__(
                self,
                singleton_service: IServiceSingleton,
                scoped_service: IServiceScoped,
            ):
                self.singleton_service = singleton_service
                self.scoped_service = scoped_service

        self.container.register(IServiceSingleton, lifestyle=LifeStyle.SINGLETON)
        self.container.register(IServiceScoped, lifestyle=LifeStyle.SCOPED)
        self.container.register(ConsumerService)

        scope1 = self.container.create_scope()
        consumer1 = scope1.resolve(ConsumerService)
        singleton_id_1 = consumer1.singleton_service.id
        scoped_id_1 = consumer1.scoped_service.id

        scope2 = self.container.create_scope()
        consumer2 = scope2.resolve(ConsumerService)
        singleton_id_2 = consumer2.singleton_service.id
        scoped_id_2 = consumer2.scoped_service.id

        self.assertEqual(singleton_id_1, singleton_id_2)
        self.assertNotEqual(scoped_id_1, scoped_id_2)

    def test_resolution_order(self):
        self.container.register(ServiceE_order)
        self.container.register(ServiceD_order)

        service_d = self.container.resolve(ServiceD_order)
        self.assertEqual(service_d.service_e.value, "Service E")

    def test_factory_with_dependencies(self):
        class IDependency(ABC):
            @abstractmethod
            def get_value(self) -> int: ...

        class Dependency(IDependency):
            def get_value(self) -> int:
                return 99

        class IService(ABC):
            @abstractmethod
            def get_combined_value(self): ...

        def factory(dependency: IDependency):
            class Service(IService):
                def get_combined_value(self):
                    return f"Combined value is {dependency.get_value() + 1}"

            return Service()

        self.container.register(IDependency, Dependency)
        self.container.register_factory(IService, factory)

        service = self.container.resolve(IService)
        result = service.get_combined_value()
        self.assertEqual(result, "Combined value is 100")

    def test_exception_on_invalid_factory(self):
        with self.assertRaises(ValueError) as context:
            self.container.register_factory("SomeInterface", "NotACallable")  # type: ignore
        self.assertIn("Factory must be callable", str(context.exception))

    def test_optional_dependency_not_registered(self):
        class IService(ABC): ...

        class Consumer:
            def __init__(self, service: IService | None = None):
                self.service = service

        self.container.register(Consumer)
        consumer = self.container.resolve(Consumer)
        self.assertIsNone(consumer.service)

    def test_property_injection_with_unregistered_dependency(self):
        class Consumer:
            @inject
            @abstractmethod
            def dependency(self) -> DependencyUnregistered: ...

        self.container.register(Consumer)

        with self.assertRaises(ServiceNotRegisteredException) as context:
            self.container.resolve(Consumer)
        message = str(context.exception)
        self.assertIn("DependencyUnregistered", message)
        self.assertIn("Consumer.dependency", message)  # names the requiring site

    def test_cyclic_dependency_with_property_injection(self):
        self.container.register(ServiceA_prop_inj)
        self.container.register(ServiceB_prop_inj)

        with self.assertRaises(CyclicDependencyException) as context:
            self.container.resolve(ServiceA_prop_inj)
        self.assertIn("Cyclic dependency detected", str(context.exception))

    def test_custom_exception_handling(self):
        class CustomException(DIException): ...

        class FaultyService:
            def __init__(self):
                raise CustomException("Custom error occurred.")

        self.container.register(FaultyService)

        with self.assertRaises(CustomException) as context:
            self.container.resolve(FaultyService)
        self.assertIn("Custom error occurred.", str(context.exception))

    def test_resolve_all_with_multiple_implementations(self):
        class IService(ABC):
            @abstractmethod
            def process(self): ...

        class ImplOne(IService):
            def process(self):
                return "Implementation One"

        class ImplTwo(IService):
            def process(self):
                return "Implementation Two"

        self.container.register(IService, ImplOne)
        self.container.register(IService, ImplTwo)

        services = self.container.resolve_all(IService)
        results = [service.process() for service in services]

        self.assertEqual(len(services), 2)
        self.assertIn("Implementation One", results)
        self.assertIn("Implementation Two", results)

    def test_resolve_all_with_no_implementations(self):
        class IService(ABC):
            @abstractmethod
            def process(self): ...

        services = self.container.resolve_all(IService)
        self.assertEqual(services, [])

    def test_resolve_all_with_named_implementations(self):
        class IService(ABC):
            @abstractmethod
            def process(self): ...

        class ImplOne(IService):
            def process(self):
                return "Implementation One"

        class ImplTwo(IService):
            def process(self):
                return "Implementation Two"

        self.container.register(IService, ImplOne, name="one")
        self.container.register(IService, ImplTwo, name="two")

        services_all = self.container.resolve_all(IService)
        self.assertEqual(len(services_all), 0)  # No unnamed registrations

        service_one = self.container.resolve(IService, name="one")
        service_two = self.container.resolve(IService, name="two")

        self.assertEqual(service_one.process(), "Implementation One")
        self.assertEqual(service_two.process(), "Implementation Two")

    def test_resolve_all_with_mixed_lifestyles(self):
        class IService(ABC):
            @abstractmethod
            def get_id(self): ...

        class ImplSingleton(IService):
            def __init__(self):
                self.id = id(self)

            def get_id(self):
                return self.id

        class ImplTransient(IService):
            def __init__(self):
                self.id = id(self)

            def get_id(self):
                return self.id

        self.container.register(IService, ImplSingleton, lifestyle=LifeStyle.SINGLETON)
        self.container.register(IService, ImplTransient, lifestyle=LifeStyle.TRANSIENT)

        services_first_call = self.container.resolve_all(IService)
        services_second_call = self.container.resolve_all(IService)

        self.assertEqual(len(services_first_call), 2)
        self.assertEqual(len(services_second_call), 2)

        singleton_ids = [
            s.get_id() for s in services_first_call if isinstance(s, ImplSingleton)
        ]
        transient_ids_first = [
            s.get_id() for s in services_first_call if isinstance(s, ImplTransient)
        ]
        transient_ids_second = [
            s.get_id() for s in services_second_call if isinstance(s, ImplTransient)
        ]

        self.assertEqual(singleton_ids[0], services_second_call[0].get_id())
        self.assertNotEqual(transient_ids_first[0], transient_ids_second[0])

    def test_resolve_all_with_factories(self):
        class IService(ABC):
            @abstractmethod
            def get_value(self): ...

        class ServiceA(IService):
            def __init__(self):
                self.value = "A"

            def get_value(self):
                return self.value

        class ServiceB(IService):
            def __init__(self):
                self.value = "B"

            def get_value(self):
                return self.value

        def factory_a():
            return ServiceA()

        def factory_b():
            return ServiceB()

        self.container.register_factory(IService, factory_a)
        self.container.register_factory(IService, factory_b)

        services = self.container.resolve_all(IService)
        values = [service.get_value() for service in services]

        self.assertEqual(len(services), 2)
        self.assertIn("A", values)
        self.assertIn("B", values)

    def test_resolve_all_with_scoped_lifestyle(self):
        class IService(ABC):
            @abstractmethod
            def get_id(self): ...

        class Service(IService):
            def __init__(self):
                self.id = id(self)

            def get_id(self):
                return self.id

        self.container.register(IService, Service, lifestyle=LifeStyle.SCOPED)

        scope1 = self.container.create_scope()
        services1 = scope1.resolve_all(IService)
        services1_again = scope1.resolve_all(IService)
        self.assertEqual(len(services1), 1)
        self.assertIs(services1[0], services1_again[0])

        scope2 = self.container.create_scope()
        services2 = scope2.resolve_all(IService)
        self.assertIsNot(services1[0], services2[0])

    def test_resolve_all_with_duplicate_implementations(self):
        class IService(ABC):
            @abstractmethod
            def process(self): ...

        class Impl(IService):
            def process(self):
                return "Implementation"

        self.container.register(IService, Impl)
        self.container.register(IService, Impl)

        services = self.container.resolve_all(IService)
        self.assertEqual(len(services), 2)
        self.assertNotEqual(services[0], services[1])  # Should be different instances

    def test_resolve_all_with_instances(self):
        class IService(ABC):
            @abstractmethod
            def get_value(self): ...

        class Service(IService):
            def __init__(self, value):
                self.value = value

            def get_value(self):
                return self.value

        instance1 = Service(1)
        instance2 = Service(2)

        self.container.add_instance(IService, instance1)
        self.container.add_instance(IService, instance2)

        services = self.container.resolve_all(IService)
        values = [service.get_value() for service in services]

        self.assertEqual(len(services), 2)
        self.assertIn(1, values)
        self.assertIn(2, values)
        self.assertIn(instance1, services)
        self.assertIn(instance2, services)

    def test_resolve_all_with_no_registrations(self):
        class IService(ABC):
            @abstractmethod
            def do_something(self): ...

        services = self.container.resolve_all(IService)
        self.assertEqual(services, [])

    def test_resolve_all_with_named_and_unnamed_registrations(self):
        class IService(ABC):
            @abstractmethod
            def get_name(self): ...

        class NamedService(IService):
            def __init__(self, name: str):
                self.name = name

            def get_name(self):
                return self.name

        self.container.register_factory(IService, lambda: NamedService("Unnamed"))
        self.container.register_factory(
            IService, lambda: NamedService("Named One"), name="one"
        )
        self.container.register_factory(
            IService, lambda: NamedService("Named Two"), name="two"
        )

        all_services = self.container.resolve_all(IService)
        self.assertEqual(len(all_services), 1)
        self.assertEqual(all_services[0].get_name(), "Unnamed")

        named_services = []
        for name in ["one", "two"]:
            service = self.container.resolve(IService, name=name)
            named_services.append(service)

        names = [s.get_name() for s in named_services]
        self.assertIn("Named One", names)
        self.assertIn("Named Two", names)

    def test_resolve_all_with_cyclic_dependency(self):
        self.container.register(ServiceA_cyclic)
        self.container.register(ServiceB_cyclic)
        self.container.register(ServiceC_cyclic)

        with self.assertRaises(CyclicDependencyException) as context:
            self.container.resolve_all(ServiceA_cyclic)
        self.assertIn("Cyclic dependency detected", str(context.exception))

    def test_resolve_all_with_different_lifestyles(self):
        class IService(ABC):
            @abstractmethod
            def get_id(self): ...

        class SingletonService(IService):
            def __init__(self):
                self.id = id(self)

            def get_id(self):
                return self.id

        class TransientService(IService):
            def __init__(self):
                self.id = id(self)

            def get_id(self):
                return self.id

        class ScopedService(IService):
            def __init__(self):
                self.id = id(self)

            def get_id(self):
                return self.id

        self.container.register(
            IService, SingletonService, lifestyle=LifeStyle.SINGLETON
        )
        self.container.register(
            IService, TransientService, lifestyle=LifeStyle.TRANSIENT
        )
        self.container.register(IService, ScopedService, lifestyle=LifeStyle.SCOPED)

        scope1 = self.container.create_scope()
        services1 = scope1.resolve_all(IService)
        services1_again = scope1.resolve_all(IService)

        singleton_services1 = [s for s in services1 if isinstance(s, SingletonService)]
        singleton_services1_again = [
            s for s in services1_again if isinstance(s, SingletonService)
        ]
        self.assertIs(singleton_services1[0], singleton_services1_again[0])

        scoped_services1 = [s for s in services1 if isinstance(s, ScopedService)]
        scoped_services1_again = [
            s for s in services1_again if isinstance(s, ScopedService)
        ]
        self.assertIs(scoped_services1[0], scoped_services1_again[0])

        transient_services1 = [s for s in services1 if isinstance(s, TransientService)]
        transient_services1_again = [
            s for s in services1_again if isinstance(s, TransientService)
        ]
        self.assertIsNot(transient_services1[0], transient_services1_again[0])

        scope2 = self.container.create_scope()
        services2 = scope2.resolve_all(IService)

        scoped_services2 = [s for s in services2 if isinstance(s, ScopedService)]
        self.assertIsNot(scoped_services1[0], scoped_services2[0])

    def test_resolve_all_with_unregistered_interface(self):
        class IService(ABC):
            @abstractmethod
            def do_something(self): ...

        services = self.container.resolve_all(IService)
        self.assertEqual(services, [])

    def test_resolve_all_with_mixed_registration_types(self):
        class IService(ABC):
            @abstractmethod
            def get_value(self): ...

        class ServiceA(IService):
            def __init__(self, value: str = "A"):
                self.value = value

            def get_value(self):
                return self.value

        class ServiceB(IService):
            def __init__(self, value: str = "B"):
                self.value = value

            def get_value(self):
                return self.value

        def factory_service_c():
            class ServiceC(IService):
                def __init__(self, value: str = "C"):
                    self.value = value

                def get_value(self):
                    return self.value

            return ServiceC()

        instance_service_d = ServiceA("D")

        self.container.register(IService, ServiceA)
        self.container.register_factory(IService, factory_service_c)
        self.container.add_instance(IService, instance_service_d)
        self.container.register(IService, ServiceB)

        services = self.container.resolve_all(IService)
        values = [service.get_value() for service in services]

        self.assertEqual(len(services), 4)
        self.assertIn("A", values)
        self.assertIn("B", values)
        self.assertIn("C", values)
        self.assertIn("D", values)

    def test_resolve_all_with_named_instances(self):
        class IService(ABC):
            @abstractmethod
            def get_value(self): ...

        class Service(IService):
            def __init__(self, value):
                self.value = value

            def get_value(self):
                return self.value

        instance1 = Service("Instance One")
        instance2 = Service("Instance Two")

        self.container.add_instance(IService, instance1, name="one")
        self.container.add_instance(IService, instance2, name="two")

        services = self.container.resolve_all(IService)
        self.assertEqual(len(services), 0)

        service_one = self.container.resolve(IService, name="one")
        service_two = self.container.resolve(IService, name="two")

        self.assertEqual(service_one.get_value(), "Instance One")
        self.assertEqual(service_two.get_value(), "Instance Two")

    def test_resolve_all_with_multiple_factories(self):
        class IService(ABC):
            @abstractmethod
            def get_value(self): ...

        def factory_service_a():
            class ServiceA(IService):
                def get_value(self):
                    return "A"

            return ServiceA()

        def factory_service_b():
            class ServiceB(IService):
                def get_value(self):
                    return "B"

            return ServiceB()

        self.container.register_factory(IService, factory_service_a)
        self.container.register_factory(IService, factory_service_b)

        services = self.container.resolve_all(IService)
        values = [service.get_value() for service in services]

        self.assertEqual(len(services), 2)
        self.assertIn("A", values)
        self.assertIn("B", values)

    def test_resolve_all_with_exception_in_factory(self):
        class IService(ABC):
            @abstractmethod
            def do_something(self): ...

        def faulty_factory():
            raise Exception("Factory error")

        self.container.register_factory(IService, faulty_factory)

        with self.assertRaises(Exception) as context:
            self.container.resolve_all(IService)
        self.assertIn("Factory error", str(context.exception))

    def test_override_instance_is_restored_after_context(self):
        class Gateway:
            def charge(self) -> str:
                return "real"

        class FakeGateway:
            def charge(self) -> str:
                return "fake"

        self.container.add_singleton(Gateway)
        real_gateway = self.container.resolve(Gateway)
        fake_gateway = FakeGateway()

        with self.container.override(Gateway, instance=fake_gateway):
            self.assertIs(self.container.resolve(Gateway), fake_gateway)
            self.assertEqual(self.container.resolve(Gateway).charge(), "fake")

        self.assertIs(self.container.resolve(Gateway), real_gateway)
        self.assertEqual(self.container.resolve(Gateway).charge(), "real")

    def test_override_implementation(self):
        class IService(ABC):
            @abstractmethod
            def get_value(self) -> str: ...

        class RealService(IService):
            def get_value(self) -> str:
                return "real"

        class FakeService(IService):
            def get_value(self) -> str:
                return "fake"

        self.container.add_transient(IService, RealService)

        with self.container.override(IService, FakeService):
            self.assertIsInstance(self.container.resolve(IService), FakeService)
            self.assertEqual(self.container.resolve(IService).get_value(), "fake")

        self.assertIsInstance(self.container.resolve(IService), RealService)

    def test_override_factory_with_dependencies(self):
        class Dependency:
            def get_value(self) -> int:
                return 7

        class IService(ABC):
            @abstractmethod
            def get_value(self) -> int: ...

        class Service(IService):
            def get_value(self) -> int:
                return 1

        class FactoryService(IService):
            def __init__(self, dependency: Dependency):
                self.dependency = dependency

            def get_value(self) -> int:
                return self.dependency.get_value()

        def factory(dependency: Dependency) -> IService:
            return FactoryService(dependency)

        self.container.add_singleton(Dependency)
        self.container.add_transient(IService, Service)

        with self.container.override(IService, factory=factory):
            self.assertEqual(self.container.resolve(IService).get_value(), 7)

        self.assertEqual(self.container.resolve(IService).get_value(), 1)

    def test_nested_override_restores_outer_override_then_original(self):
        class Gateway:
            def get_value(self) -> str:
                return "real"

        class OuterGateway:
            def get_value(self) -> str:
                return "outer"

        class InnerGateway:
            def get_value(self) -> str:
                return "inner"

        self.container.add_transient(Gateway)

        with self.container.override(Gateway, OuterGateway):
            self.assertIsInstance(self.container.resolve(Gateway), OuterGateway)
            self.assertEqual(self.container.resolve(Gateway).get_value(), "outer")

            with self.container.override(Gateway, InnerGateway):
                self.assertIsInstance(self.container.resolve(Gateway), InnerGateway)
                self.assertEqual(self.container.resolve(Gateway).get_value(), "inner")

            self.assertIsInstance(self.container.resolve(Gateway), OuterGateway)
            self.assertEqual(self.container.resolve(Gateway).get_value(), "outer")

        self.assertIsInstance(self.container.resolve(Gateway), Gateway)
        self.assertEqual(self.container.resolve(Gateway).get_value(), "real")

    def test_nested_override_restores_singleton_instances(self):
        class Service:
            def __init__(self, value: str):
                self.value = value

        class RealService(Service):
            def __init__(self):
                super().__init__("real")

        class OuterService(Service):
            def __init__(self):
                super().__init__("outer")

        class InnerService(Service):
            def __init__(self):
                super().__init__("inner")

        self.container.add_singleton(Service, RealService)
        real_service = self.container.resolve(Service)

        with self.container.override(
            Service, OuterService, lifestyle=LifeStyle.SINGLETON
        ):
            outer_service = self.container.resolve(Service)
            self.assertIs(outer_service, self.container.resolve(Service))
            self.assertEqual(outer_service.value, "outer")

            with self.container.override(
                Service, InnerService, lifestyle=LifeStyle.SINGLETON
            ):
                inner_service = self.container.resolve(Service)
                self.assertIs(inner_service, self.container.resolve(Service))
                self.assertIsNot(inner_service, outer_service)
                self.assertEqual(inner_service.value, "inner")

            self.assertIs(self.container.resolve(Service), outer_service)
            self.assertEqual(self.container.resolve(Service).value, "outer")

        self.assertIs(self.container.resolve(Service), real_service)
        self.assertEqual(self.container.resolve(Service).value, "real")

    def test_override_rejects_multiple_targets(self):
        class Service: ...

        with self.assertRaises(ValueError) as context:
            self.container.override(Service, Service, instance=Service())

        self.assertIn("Provide only one override target", str(context.exception))

    def test_validate_returns_empty_list_for_valid_graph(self):
        class Repository: ...

        class Service:
            def __init__(self, repository: Repository):
                self.repository = repository

        self.container.add_singleton(Repository)
        self.container.add_transient(Service)

        self.assertEqual(self.container.validate(), [])

    def test_validate_reports_missing_constructor_dependency(self):
        class Repository: ...

        class Service:
            def __init__(self, repository: Repository):
                self.repository = repository

        self.container.add_transient(Service)

        errors = self.container.validate()

        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ValidationError)
        self.assertEqual(errors[0].service, Service)
        self.assertIn("Dependency 'repository' is not registered", errors[0].message)

    def test_validate_allows_optional_or_default_dependency(self):
        class Cache: ...

        class Service:
            def __init__(self, cache: Cache | None = None):
                self.cache = cache

        self.container.add_transient(Service)

        self.assertEqual(self.container.validate(), [])

    def test_validate_reports_factory_dependency_errors(self):
        class Settings: ...

        class Client: ...

        def factory(settings: Settings) -> Client:
            return Client()

        self.container.add_transient_factory(Client, factory)

        errors = self.container.validate()

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].service, Client)
        self.assertIn("Dependency 'settings' is not registered", errors[0].message)

    def test_validate_detects_cycles_without_instantiating_services(self):
        class ServiceA:
            created = False

            def __init__(self, service_b: "ServiceB"):
                ServiceA.created = True
                self.service_b = service_b

        class ServiceB:
            def __init__(self, service_a: ServiceA):
                self.service_a = service_a

        self.container.add_transient(ServiceA)
        self.container.add_transient(ServiceB)

        errors = self.container.validate()

        self.assertFalse(ServiceA.created)
        self.assertTrue(
            any("Cyclic dependency detected" in error.message for error in errors)
        )

    def test_assert_valid_raises_container_validation_exception(self):
        class Dependency: ...

        class Service:
            def __init__(self, dependency: Dependency):
                self.dependency = dependency

        self.container.add_transient(Service)

        with self.assertRaises(ContainerValidationException) as context:
            self.container.assert_valid()

        self.assertEqual(len(context.exception.errors), 1)
        self.assertIn("Container validation failed", str(context.exception))

    def test_override_invalidates_cached_resolution_plan(self):
        class Service:
            value = "real"

        class FakeService:
            value = "fake"

        class Consumer:
            def __init__(self, service: Service):
                self.service = service

        self.container.add_transient(Service)
        self.container.add_transient(Consumer)

        self.assertEqual(self.container.resolve(Consumer).service.value, "real")

        with self.container.override(Service, FakeService):
            self.assertEqual(self.container.resolve(Consumer).service.value, "fake")

        self.assertEqual(self.container.resolve(Consumer).service.value, "real")

    def test_unhashable_callable_factory_resolves(self):
        class Service: ...

        class Factory:
            def __eq__(self, other):
                return isinstance(other, Factory)

            def __call__(self) -> Service:
                return Service()

        self.container.add_transient_factory(Service, Factory())

        self.assertIsInstance(self.container.resolve(Service), Service)

    def test_optional_injected_property_defaults_to_none(self):
        class Cache: ...

        class Service:
            @inject
            @abstractmethod
            def cache(self) -> Cache | None: ...

        self.container.add_transient(Service)

        self.assertIsNone(self.container.resolve(Service).cache)

    def test_reentrant_container_resolution_detects_cycle(self):
        class Service:
            def __init__(self, container):
                container.resolve(Service)

        self.container.add_transient(Service)

        with self.assertRaises(CyclicDependencyException):
            self.container.resolve(Service)

    def test_public_api_all_exports_core_symbols(self):
        expected = {
            "Container",
            "ContainerValidationException",
            "CyclicDependencyException",
            "DIException",
            "InvalidLifestyleException",
            "LifeStyle",
            "MissingTypeAnnotationException",
            "Scope",
            "ServiceNotRegisteredException",
            "ValidationError",
            "inject",
        }

        self.assertTrue(expected.issubset(set(injex.__all__)))


if __name__ == "__main__":
    unittest.main()
