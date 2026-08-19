"""
Money, the payment authority, and violations.

A payment authority is what the human signs in advance. It says who may spend, how
much, at which shops, in which categories, and until when.

It is NOT a shopping list. It never mentions products. By the time this system runs,
the cart is already full and somebody else chose what is in it.

One rule throughout: money is stored as whole paise, never as a decimal fraction.
A payments system that rounds is a payments system that can be gamed by rounding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Iterable


@dataclass(frozen=True, order=True)
class Money:
    """Rupees, stored as whole paise. Rs 54.00 is stored as 5400."""

    paise: int

    @classmethod
    def rupees(cls, amount: Decimal | int | str) -> "Money":
        return cls(int((Decimal(str(amount)) * 100).to_integral_value()))

    def __add__(self, other: "Money") -> "Money":
        return Money(self.paise + other.paise)

    def __sub__(self, other: "Money") -> "Money":
        return Money(self.paise - other.paise)

    def __str__(self) -> str:
        return f"Rs {self.paise / 100:,.2f}"

    def __repr__(self) -> str:
        return f"Money({self})"


class Severity(str, Enum):
    #: the payment must not go through
    FATAL = "fatal"
    #: the payment goes through, but the agent's record notes it
    WARN = "warn"


@dataclass(frozen=True)
class Violation:
    """One reason a payment was refused, in a form a dispute can quote."""

    kind: str
    detail: str
    expected: str
    actual: str
    severity: Severity = Severity.FATAL

    def __str__(self) -> str:
        mark = "FATAL" if self.severity is Severity.FATAL else "warn "
        return f"[{mark}] {self.kind}: {self.detail} (expected {self.expected}, got {self.actual})"


@dataclass(frozen=True)
class PaymentAuthority:
    """
    What the human signed, in advance.

    Every field is a ceiling or an allow-list. There is deliberately no way to say
    "prefer" or "roughly". A bank cannot refuse a payment on a probability, so every
    condition here has to be checkable by arithmetic alone.

    `valid_from` and `valid_until` are integer ticks on a simulated clock, not real
    timestamps. Real time is not needed to model a revocation arriving one tick before
    a payment.
    """

    #: most that may be spent in any one payment
    max_per_payment: Money
    #: most that may be spent in total, across every payment made under this authority
    max_total: Money
    #: shops this authority may be spent at. empty means any shop.
    allowed_merchants: frozenset[str] = field(default_factory=frozenset)
    #: categories this authority covers. None means any category.
    allowed_categories: frozenset[str] | None = None
    #: how many separate payments may be made. stops an agent retrying forever.
    max_payments: int = 1
    valid_from: int = 0
    valid_until: int = 1_000

    @classmethod
    def build(
        cls,
        max_per_payment: Decimal | int | str,
        max_total: Decimal | int | str,
        allowed_merchants: Iterable[str] = (),
        allowed_categories: Iterable[str] | None = None,
        max_payments: int = 1,
        valid_from: int = 0,
        valid_until: int = 1_000,
    ) -> "PaymentAuthority":
        return cls(
            max_per_payment=Money.rupees(max_per_payment),
            max_total=Money.rupees(max_total),
            allowed_merchants=frozenset(allowed_merchants),
            allowed_categories=(frozenset(allowed_categories)
                                if allowed_categories is not None else None),
            max_payments=max_payments,
            valid_from=valid_from,
            valid_until=valid_until,
        )

    def to_dict(self) -> dict:
        return {
            "max_per_payment_paise": self.max_per_payment.paise,
            "max_total_paise": self.max_total.paise,
            "allowed_merchants": sorted(self.allowed_merchants),
            "allowed_categories": (sorted(self.allowed_categories)
                                   if self.allowed_categories is not None else None),
            "max_payments": self.max_payments,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
        }

    def describe(self) -> str:
        bits = [f"<= {self.max_per_payment}/payment", f"<= {self.max_total} total"]
        if self.allowed_merchants:
            bits.append("at {" + ", ".join(sorted(self.allowed_merchants)) + "}")
        if self.allowed_categories:
            bits.append("for {" + ", ".join(sorted(self.allowed_categories)) + "}")
        bits.append(f"max {self.max_payments} payment(s)")
        bits.append(f"ticks {self.valid_from}-{self.valid_until}")
        return " | ".join(bits)
