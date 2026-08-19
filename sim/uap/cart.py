"""
The cart, and the request to pay for it.

A cart arrives already filled. This simulation never builds one by searching or
comparing prices, because that happens before the boundary being studied here.

Two objects:

    Cart            what is being paid for, to whom, how much, agreed at tick T
    PaymentRequest  the agent asking the rail to actually move the money

They are separate on purpose. The gap between them is where price drift, payee
substitution and double debits live. If the cart and the payment were one object,
none of those attacks could even be written down.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .authority import Money


@dataclass(frozen=True)
class CartLine:
    title: str
    amount: Money

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "amount_paise": self.amount.paise}


@dataclass(frozen=True)
class Cart:
    """
    What the human (or the agent) agreed to buy, and from whom.

    `total` is stored rather than derived, so a cart whose total does not equal the
    sum of its lines can be represented. That inconsistency is an attack, and a model
    that cannot express an attack cannot test for it.
    """

    cart_id: str
    merchant: str
    category: str
    lines: tuple[CartLine, ...]
    total: Money
    agreed_at: int = 0

    @classmethod
    def build(cls, cart_id: str, merchant: str, category: str,
              lines: list[tuple[str, int | str]], total: int | str | None = None,
              agreed_at: int = 0) -> "Cart":
        parsed = tuple(CartLine(t, Money.rupees(a)) for t, a in lines)
        summed = Money(sum(l.amount.paise for l in parsed))
        return cls(
            cart_id=cart_id, merchant=merchant, category=category, lines=parsed,
            total=Money.rupees(total) if total is not None else summed,
            agreed_at=agreed_at,
        )

    @property
    def line_sum(self) -> Money:
        return Money(sum(l.amount.paise for l in self.lines))

    def to_dict(self) -> dict[str, Any]:
        return {
            "cart_id": self.cart_id,
            "merchant": self.merchant,
            "category": self.category,
            "lines": [l.to_dict() for l in self.lines],
            "total_paise": self.total.paise,
            "agreed_at": self.agreed_at,
        }

    def describe(self) -> str:
        items = ", ".join(f"{l.title} {l.amount}" for l in self.lines)
        return f"{self.merchant} [{self.category}] {items} = {self.total}"


@dataclass(frozen=True)
class PaymentRequest:
    """
    The agent asking to move money.

    It names its own merchant and amount rather than reading them from the cart. That
    is deliberate: an agent that could only ever quote the cart back correctly would
    make payee substitution impossible to test.
    """

    cart_ref: str
    merchant: str
    amount: Money
    requested_at: int = 0
    #: distinguishes two genuine payments from one payment retried
    nonce: str = "1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "cart_ref": self.cart_ref,
            "merchant": self.merchant,
            "amount_paise": self.amount.paise,
            "requested_at": self.requested_at,
            "nonce": self.nonce,
        }
