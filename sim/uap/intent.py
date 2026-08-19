"""
The constraint language.

AP2 gives you a signed envelope. It does not specify the grammar *inside* it.
This module is that grammar: the vocabulary in which a human says what an agent
may buy, precise enough that a machine can decide satisfaction without a model
in the loop.

Two design rules, both load-bearing:

1.  **Everything is exact integers.** Money is paise, mass is grams, volume is
    millilitres. No floats touch a comparison. A payments system that rounds is
    a payments system that can be gamed by rounding.

2.  **Unit normalisation is a security control, not a convenience.** A merchant
    quoting "Rs 29" for a 500g pack against a "<= Rs 56/kg" constraint is not a
    display quirk -- normalised it is Rs 58/kg, and over the ceiling. It is caught
    here, or it is not caught at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Iterable


# --------------------------------------------------------------------------
# Money
# --------------------------------------------------------------------------

@dataclass(frozen=True, order=True)
class Money:
    """Rupees, held as integer paise. Never a float."""

    paise: int

    @classmethod
    def rupees(cls, amount: Decimal | int | str) -> "Money":
        return cls(int((Decimal(str(amount)) * 100).to_integral_value()))

    def __add__(self, other: "Money") -> "Money":
        return Money(self.paise + other.paise)

    def __sub__(self, other: "Money") -> "Money":
        return Money(self.paise - other.paise)

    def __mul__(self, k: int) -> "Money":
        return Money(self.paise * k)

    def __str__(self) -> str:
        return f"Rs {self.paise / 100:,.2f}"

    def __repr__(self) -> str:
        return f"Money({self})"


# --------------------------------------------------------------------------
# Quantity
# --------------------------------------------------------------------------

class Unit(str, Enum):
    KG = "kg"
    G = "g"
    L = "l"
    ML = "ml"
    PIECE = "piece"


#: unit -> (base unit, how many base units one of it is worth)
_BASE: dict[Unit, tuple[Unit, int]] = {
    Unit.KG: (Unit.G, 1000),
    Unit.G: (Unit.G, 1),
    Unit.L: (Unit.ML, 1000),
    Unit.ML: (Unit.ML, 1),
    Unit.PIECE: (Unit.PIECE, 1),
}


@dataclass(frozen=True)
class Quantity:
    """A quantity that always knows its own base-unit value."""

    amount: Decimal
    unit: Unit

    @property
    def base_unit(self) -> Unit:
        return _BASE[self.unit][0]

    @property
    def base_amount(self) -> int:
        """Exact integer count in the base unit (grams / ml / pieces)."""
        factor = _BASE[self.unit][1]
        return int((Decimal(str(self.amount)) * factor).to_integral_value())

    def commensurable_with(self, other: "Quantity") -> bool:
        return self.base_unit == other.base_unit

    def __str__(self) -> str:
        d = Decimal(str(self.amount)).normalize()
        # normalize() renders 650 as 6.5E+2; force plain notation for integers
        if d == d.to_integral_value():
            d = d.quantize(Decimal(1))
        return f"{d}{self.unit.value}"


#: base unit -> (display unit, how many base units the display unit holds)
_DISPLAY: dict[Unit, tuple[str, int]] = {
    Unit.G: ("kg", 1000),
    Unit.ML: ("l", 1000),
    Unit.PIECE: ("piece", 1),
}


def display_unit(base: Unit) -> str:
    return _DISPLAY[base][0]


def unit_price(total: Money, qty: Quantity) -> int:
    """
    Price per *display* unit (kg / l / piece), in paise, rounded up.

    Pricing per display unit rather than per base unit is a resolution decision with
    teeth: at paise-per-gram, Rs 54/kg and Rs 59/kg both round to 6 paise/g and every
    offer in the catalogue ties. A comparison that cannot separate real prices cannot
    detect a manipulated one.

    Rounding up is deliberate -- a constraint is a ceiling, so borderline cases fail
    closed. `Rs 29 / 500g` normalises to Rs 58/kg, which is exactly what the
    unit-confusion attack is trying to hide.
    """
    if qty.base_amount <= 0:
        raise ValueError("cannot price a zero or negative quantity")
    factor = _DISPLAY[qty.base_unit][1]
    return -(-(total.paise * factor) // qty.base_amount)  # ceil division


# --------------------------------------------------------------------------
# Substitution policy
# --------------------------------------------------------------------------

class Substitution(str, Enum):
    #: the exact item, or nothing
    NONE = "none"
    #: any item sharing the canonical item key (e.g. another brand of atta)
    SAME_ITEM = "same_item"
    #: anything in the same category (atta -> maida). Deliberately permissive.
    SAME_CATEGORY = "same_category"


# --------------------------------------------------------------------------
# Violations
# --------------------------------------------------------------------------

class Severity(str, Enum):
    #: the payment must not authorise
    FATAL = "fatal"
    #: authorises, but is recorded against the agent's behavioural record
    WARN = "warn"


@dataclass(frozen=True)
class Violation:
    kind: str
    detail: str
    expected: str
    actual: str
    severity: Severity = Severity.FATAL

    def __str__(self) -> str:
        mark = "FATAL" if self.severity is Severity.FATAL else "warn "
        return f"[{mark}] {self.kind}: {self.detail} (expected {self.expected}, got {self.actual})"


# --------------------------------------------------------------------------
# The intent itself
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Intent:
    """
    What the human authorised. Signed into an Intent Mandate and never mutated.

    Every field is a *ceiling* or an *allow-list*. There is deliberately no way to
    express "prefer" or "roughly" -- a preference cannot be checked deterministically,
    and anything that cannot be checked deterministically cannot gate a payment.
    """

    item: str
    max_quantity: Quantity
    max_total: Money
    #: paise per *display* unit (kg / l / piece); None means unconstrained
    max_unit_price: int | None = None
    allowed_merchants: frozenset[str] = field(default_factory=frozenset)
    substitution: Substitution = Substitution.NONE
    #: tolerated drift between the price quoted at discovery and the price charged
    max_price_drift_bps: int = 0
    #: how many times this intent may be exercised before it must be re-signed
    max_executions: int = 1

    # -- construction helper -------------------------------------------------

    @classmethod
    def build(
        cls,
        item: str,
        max_quantity: Quantity,
        max_total: Decimal | int | str,
        max_unit_price_per: tuple[Decimal | int | str, Unit] | None = None,
        allowed_merchants: Iterable[str] = (),
        substitution: Substitution = Substitution.NONE,
        max_price_drift_bps: int = 0,
        max_executions: int = 1,
    ) -> "Intent":
        """
        Ergonomic constructor. `max_unit_price_per=(60, Unit.KG)` means Rs 60/kg,
        stored normalised as 6000 paise per kg.
        """
        unit_ceiling = None
        if max_unit_price_per is not None:
            amount, per = max_unit_price_per
            one = Quantity(Decimal(1), per)
            unit_ceiling = unit_price(Money.rupees(amount), one)
        return cls(
            item=item,
            max_quantity=max_quantity,
            max_total=Money.rupees(max_total),
            max_unit_price=unit_ceiling,
            allowed_merchants=frozenset(allowed_merchants),
            substitution=substitution,
            max_price_drift_bps=max_price_drift_bps,
            max_executions=max_executions,
        )

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "item": self.item,
            "max_quantity": {
                "amount": str(self.max_quantity.amount),
                "unit": self.max_quantity.unit.value,
            },
            "max_total_paise": self.max_total.paise,
            "max_unit_price_paise_per_base": self.max_unit_price,
            "allowed_merchants": sorted(self.allowed_merchants),
            "substitution": self.substitution.value,
            "max_price_drift_bps": self.max_price_drift_bps,
            "max_executions": self.max_executions,
        }

    def describe(self) -> str:
        bits = [f"{self.item} <= {self.max_quantity}"]
        if self.max_unit_price is not None:
            bits.append(f"<= {Money(self.max_unit_price)}/{display_unit(self.max_quantity.base_unit)}")
        bits.append(f"total <= {self.max_total}")
        if self.allowed_merchants:
            bits.append("sellers in {" + ", ".join(sorted(self.allowed_merchants)) + "}")
        if self.substitution is not Substitution.NONE:
            bits.append(f"substitution={self.substitution.value}")
        return " | ".join(bits)
