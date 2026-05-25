from typing import Protocol

from injex import Container


class PaymentGateway(Protocol):
    def charge(self, amount: int) -> str: ...


class StripeGateway:
    def charge(self, amount: int) -> str:
        return f"charged {amount} via Stripe"


class FakePaymentGateway:
    def __init__(self):
        self.charges: list[int] = []

    def charge(self, amount: int) -> str:
        self.charges.append(amount)
        return "test-payment-id"


class Checkout:
    def __init__(self, payments: PaymentGateway):
        self.payments = payments

    def pay(self, amount: int) -> str:
        return self.payments.charge(amount)


container = Container()
container.add_singleton(PaymentGateway, StripeGateway)
container.add_transient(Checkout)

fake_payments = FakePaymentGateway()

with container.override(PaymentGateway, instance=fake_payments):
    checkout = container.resolve(Checkout)
    payment_id = checkout.pay(1999)

assert payment_id == "test-payment-id"
assert fake_payments.charges == [1999]
