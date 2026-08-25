"""
The order, and the gate that binds a payment to it.

This is the piece the rest of the simulator was missing. The mandate says how much
the user *may* spend and with whom. The policy says what the operator permits. Neither
of them knows what the user actually agreed to buy.

So a mandate for Rs 5,000 to `brewhouse@ybl` happily authorises a Rs 600 payment to
`brewhouse@ybl` — even when the basket the human saw came to Rs 118. Every limit is
respected and the user is still overcharged. There is nothing in the system that holds
a record of the agreement to compare against.

An **Order** is that record: what was agreed, with whom, for how much, and when.
`validate_order` is the gate that checks the payment still matches it.

## Who signs the order

This is the open question, so it is a setting rather than a decision:

    AGENT     the agent can write whatever it likes into the order
    MERCHANT  the shop can write whatever it likes into the order
    BOTH      neither can produce an order alone -- but the shop has to take part,
              and no shop integrates with a scheme that does not exist yet

The simulation's finding is that this matters less than expected. A *self-consistent*
inflated order passes all three, because a signature proves who wrote a record, not
that the record is true. What refuses it is a tight per-transaction ceiling on the
mandate. See `tests/test_consent.py`.

Signing is Ed25519, a public-key scheme: each party holds a private key nobody else
has, so a signature identifies its author. It is deliberately not a shared secret --
if the user and the agent shared one, the agent could forge the user's own consent and
the whole argument collapses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from typing import Any

from core import Money, validate_vpa
from models import iso, utcnow

from identity import CRYPTO, PublicKey, Resolver, Signer  # noqa: F401


# --------------------------------------------------------------------------
# Keys and signing
# --------------------------------------------------------------------------

class Keypair(Signer):
    """One party's private key. The name it signs under is `label`.

    This used to verify its own signatures by reaching for `self._private`, which
    was fine while the only question was *what does a signature prove*. It is not
    fine for anything a third party has to check, so the two halves now live in
    `identity.py` and this is the private one.

    Verification belongs to `identity.Resolver`, which holds public keys only.
    """

    def __repr__(self) -> str:
        return f"Keypair({self.label})"


def canonical(payload: dict[str, Any]) -> bytes:
    """
    Serialise the same way every time.

    Without this the same order could be written two different ways and a perfectly
    valid signature would fail to verify.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


class OrderSigner(str, Enum):
    AGENT = "agent"
    MERCHANT = "merchant"
    BOTH = "both"


# --------------------------------------------------------------------------
# The order
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class OrderLine:
    title: str
    amount: Money

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "amount_paise": self.amount.paise}


# --------------------------------------------------------------------------
# Metered purchases
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Tariff:
    """What the user agreed to pay per unit, and the most they agreed to spend.

    Some purchases have no basket. A charging session, a battery swap, a tanker of
    water: the amount depends on a quantity nobody knows until the thing is over.
    Those are the machine events the beachhead use cases are built on, and an
    agreed total cannot describe them.

    So the user agrees a **rate** and a **ceiling** instead. At settlement the
    meter supplies a quantity, and the payment must equal rate times quantity and
    stay under the ceiling. That is still arithmetic, so the approval path stays
    deterministic and a refusal still carries a reason you can put in a dispute.

    The ceiling is what does the protecting. `max_quantity` is optional and only
    catches a runaway meter, which is a different failure from an inflated rate.
    """

    rate: Money
    unit: str
    cap: Money
    max_quantity: str | None = None

    def expected(self, quantity) -> Money:
        """What this tariff says a given quantity should cost."""
        return self.rate.times(quantity)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rate_paise": self.rate.paise,
            "unit": self.unit,
            "cap_paise": self.cap.paise,
            "max_quantity": self.max_quantity,
        }


@dataclass
class Order:
    """
    What the human agreed to buy, and from whom.

    `total` is stored rather than derived from the lines. That is deliberate: an order
    whose total disagrees with its own lines is an attack, and a model that cannot
    represent an attack cannot test for it.
    """

    order_id: str
    payee_vpa: str
    lines: tuple[OrderLine, ...]
    total: Money
    agreed_at: Any = field(default_factory=utcnow)
    category: str = "general"
    #: set for a metered purchase. When present, `total` is an estimate and not
    #: the agreement. The tariff is the agreement.
    tariff: "Tariff | None" = None
    signatures: dict[str, bytes] = field(default_factory=dict)

    @property
    def is_metered(self) -> bool:
        return self.tariff is not None

    @classmethod
    def build(cls, order_id: str, payee_vpa: str,
              lines: list[tuple[str, str | int]],
              total: str | int | None = None,
              category: str = "general", agreed_at: Any = None) -> "Order":
        parsed = tuple(OrderLine(t, Money.rupees(str(a))) for t, a in lines)
        summed = Money(sum(l.amount.paise for l in parsed))
        return cls(
            order_id=order_id, payee_vpa=validate_vpa(payee_vpa), lines=parsed,
            total=Money.rupees(str(total)) if total is not None else summed,
            agreed_at=agreed_at or utcnow(), category=category,
        )

    @classmethod
    def metered(cls, order_id: str, payee_vpa: str, description: str,
                rate: str | int, unit: str, cap: str | int,
                max_quantity: str | None = None,
                category: str = "general", agreed_at: Any = None) -> "Order":
        """An order for something measured rather than itemised.

        `total` is set to the ceiling so anything reading it without knowing about
        tariffs sees the worst case rather than a smaller number it might trust.
        """
        tariff = Tariff(
            rate=Money.rupees(str(rate)), unit=unit,
            cap=Money.rupees(str(cap)), max_quantity=max_quantity,
        )
        return cls(
            order_id=order_id, payee_vpa=validate_vpa(payee_vpa),
            lines=(OrderLine(description, tariff.cap),),
            total=tariff.cap, agreed_at=agreed_at or utcnow(),
            category=category, tariff=tariff,
        )

    @property
    def line_sum(self) -> Money:
        return Money(sum(l.amount.paise for l in self.lines))

    def payload(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "payee_vpa": self.payee_vpa,
            "lines": [l.to_dict() for l in self.lines],
            "total_paise": self.total.paise,
            "agreed_at": iso(self.agreed_at),
            "category": self.category,
            # the tariff is signed. a rate that could be swapped after the fact
            # would make the ceiling the only real protection.
            "tariff": self.tariff.to_dict() if self.tariff else None,
        }

    def sign(self, signer: OrderSigner, agent: Keypair, merchant: Keypair) -> "Order":
        blob = canonical(self.payload())
        who = {OrderSigner.AGENT: [agent],
               OrderSigner.MERCHANT: [merchant],
               OrderSigner.BOTH: [agent, merchant]}[signer]
        for k in who:
            self.signatures[k.label] = k.sign(blob)
        return self

    def tamper(self, **changes: Any) -> "Order":
        """Change the order without re-signing. Adversarial tests only."""
        o = Order(order_id=self.order_id, payee_vpa=self.payee_vpa, lines=self.lines,
                  total=self.total, agreed_at=self.agreed_at, category=self.category,
                  tariff=self.tariff, signatures=dict(self.signatures))
        for k, v in changes.items():
            setattr(o, k, v)
        return o

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "signed_by": sorted(self.signatures)}


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------

def _check(name: str, passed: bool, detail: str) -> dict:
    return {"check": name, "passed": passed, "detail": detail}


#: how long after it was agreed an order may still be paid
DEFAULT_ORDER_TTL = timedelta(minutes=30)


def validate_order(
    order: Order | None,
    payee_vpa: str | None,
    amount: Money | None,
    required_signer: OrderSigner,
    resolver: Resolver,
    agent_name: str,
    merchant_name: str,
    ttl: timedelta = DEFAULT_ORDER_TTL,
    quantity: str | None = None,
) -> tuple[bool, list[str], list[dict]]:
    """
    Does this payment still match the order the human agreed to?

    Returns `(passed, reasons, checks)` rather than a Verdict, so that `policy.py`
    can fold it into the single verdict it already builds without a circular import.

    `resolver` holds **public keys only**. That is the point of it: this function is
    the thing a switch would run, and a switch that needed the agent's private key to
    check the agent's signature could equally well have forged it.
    """
    reasons: list[str] = []
    checks: list[dict] = []

    if order is None:
        return False, ["no order supplied; nothing records what the user agreed to"], \
               [_check("order_present", False, "no order")]
    checks.append(_check("order_present", True, order.order_id))

    # -- signatures ------------------------------------------------------

    blob = canonical(order.payload())
    needed = {OrderSigner.AGENT: [(agent_name, "agent")],
              OrderSigner.MERCHANT: [(merchant_name, "merchant")],
              OrderSigner.BOTH: [(agent_name, "agent"),
                                 (merchant_name, "merchant")]}[required_signer]
    for name, who in needed:
        sig = order.signatures.get(name)
        # an unregistered party fails closed: no key, no verdict, no payment
        ok = bool(sig) and resolver.verify(name, blob, sig)
        checks.append(_check(f"order_signed_by_{who}", ok,
                             f"required {required_signer.value}; "
                             f"present {sorted(order.signatures) or 'none'}"))
        if not ok:
            reasons.append(f"the order carries no valid {who} signature")

    if reasons:                       # an unverifiable order tells us nothing further
        return False, reasons, checks

    # -- the order must be internally consistent --------------------------

    consistent = order.line_sum == order.total
    checks.append(_check("order_self_consistent", consistent,
                         f"lines total {order.line_sum} against stated {order.total}"))
    if not consistent:
        reasons.append(
            f"the order's lines add to {order.line_sum} but it claims {order.total}"
        )

    # -- the payment must still match it ----------------------------------

    if amount is not None and order.is_metered:
        t = order.tariff

        # A metered purchase has no agreed total, so there is nothing to compare
        # for equality. Without a reading there is nothing to compare at all.
        if quantity is None:
            checks.append(_check("meter_reading_present", False,
                                 f"metered at {t.rate} per {t.unit}, no reading supplied"))
            reasons.append(
                f"this is metered at {t.rate} per {t.unit} and no meter reading "
                f"was supplied, so the amount cannot be checked"
            )
        else:
            checks.append(_check("meter_reading_present", True,
                                 f"{quantity} {t.unit}"))

            expected = t.expected(quantity)
            correct = amount == expected
            checks.append(_check("amount_matches_tariff", correct,
                                 f"{quantity} {t.unit} at {t.rate} comes to {expected}, "
                                 f"paying {amount}"))
            if not correct:
                reasons.append(
                    f"{quantity} {t.unit} at {t.rate} per {t.unit} comes to "
                    f"{expected}, but the payment is {amount}"
                )

            if t.max_quantity is not None:
                within_qty = Decimal(str(quantity)) <= Decimal(t.max_quantity)
                checks.append(_check("within_max_quantity", within_qty,
                                     f"{quantity} against a limit of "
                                     f"{t.max_quantity} {t.unit}"))
                if not within_qty:
                    reasons.append(
                        f"the meter read {quantity} {t.unit}, over the agreed "
                        f"limit of {t.max_quantity}"
                    )

        # The ceiling is checked whatever the reading says. It is the control the
        # user actually set, and it holds even if the meter is lying.
        under_cap = amount <= t.cap
        checks.append(_check("under_agreed_cap", under_cap,
                             f"paying {amount} against the agreed ceiling {t.cap}"))
        if not under_cap:
            reasons.append(
                f"the payment is {amount}, over the {t.cap} ceiling the user agreed"
            )

    elif amount is not None:
        matches = amount == order.total
        checks.append(_check("amount_matches_order", matches,
                             f"paying {amount} against agreed {order.total}"))
        if not matches:
            reasons.append(
                f"the payment is {amount} but the user agreed to {order.total}"
            )

    if payee_vpa is not None:
        same_payee = validate_vpa(payee_vpa) == order.payee_vpa
        checks.append(_check("payee_matches_order", same_payee,
                             f"paying {payee_vpa} against agreed {order.payee_vpa}"))
        if not same_payee:
            reasons.append(
                f"the money is going to {payee_vpa} but the order was with "
                f"{order.payee_vpa}"
            )

    # -- and it must not be stale -----------------------------------------

    age = utcnow() - order.agreed_at
    fresh = age <= ttl
    checks.append(_check("order_fresh", fresh,
                         f"agreed {int(age.total_seconds())}s ago, ttl {int(ttl.total_seconds())}s"))
    if not fresh:
        reasons.append(
            f"the order was agreed {int(age.total_seconds())}s ago, beyond its "
            f"{int(ttl.total_seconds())}s validity"
        )

    return not reasons, reasons, checks
