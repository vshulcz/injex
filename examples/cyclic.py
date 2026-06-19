"""A dependency cycle is reported up front by validate() / assert_valid(),
before any instance is constructed."""

from injex import Container, ContainerValidationException


class ServiceA:
    def __init__(self, service_b: "ServiceB"):
        self.service_b = service_b


class ServiceB:
    def __init__(self, service_a: "ServiceA"):
        self.service_a = service_a


def main() -> None:
    container = Container()
    container.add_transient(ServiceA)
    container.add_transient(ServiceB)

    # validate() finds the cycle without constructing anything.
    errors = container.validate()
    print("validation errors:", [str(e) for e in errors])

    try:
        container.assert_valid()
    except ContainerValidationException as exc:
        print("startup guard refused to run:", exc.errors[0])


if __name__ == "__main__":
    main()
