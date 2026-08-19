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
from enum import Enum
from hashlib import sha256
from typing import Any

from core import Money, validate_vpa
from models import iso, utcnow

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    CRYPTO = True
except ImportError:                                    # pragma: no cover
    CRYPTO = False


# --------------------------------------------------------------------------
# Keys and signing
# --------------------------------------------------------------------------

class Keypair:
    """One party's identity. Falls back to a stub if `cryptography` is absent."""

    def __init__(self, label: str) -> None:
        self.label = label
        self._private = Ed25519PrivateKey.generate() if CRYPTO else None

    def sign(self, blob: bytes) -> bytes:
        if not CRYPTO:                                 # pragma: no cover
            return sha256(self.label.encode() + blob).digest()
        return self._private.sign(blob)

    def verify(self, blob: bytes, signature: bytes) -> bool:
        if not CRYPTO:                                 # pragma: no cover
            return signature == sha256(self.label.encode() + blob).digest()
        try:
            self._private.public_key().verify(signature, blob)
            return True
        except InvalidSignature:
            return False

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
    signatures: dict[str, bytes] = field(default_factory=dict)

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
                  signatures=dict(self.signatures))
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
    agent_key: Keypair,
    merchant_key: Keypair,
    ttl: timedelta = DEFAULT_ORDER_TTL,
) -> tuple[bool, list[str], list[dict]]:
    """
    Does this payment still match the order the human agreed to?

    Returns `(passed, reasons, checks)` rather than a Verdict, so that `policy.py`
    can fold it into the single verdict it already builds without a circular import.
    """
    reasons: list[str] = []
    checks: list[dict] = []

    if order is None:
        return False, ["no order supplied; nothing records what the user agreed to"], \
               [_check("order_present", False, "no order")]
    checks.append(_check("order_present", True, order.order_id))

    # -- signatures ------------------------------------------------------

    blob = canonical(order.payload())
    needed = {OrderSigner.AGENT: [(agent_key, "agent")],
              OrderSigner.MERCHANT: [(merchant_key, "merchant")],
              OrderSigner.BOTH: [(agent_key, "agent"), (merchant_key, "merchant")]}[required_signer]
    for key, who in needed:
        sig = order.signatures.get(key.label)
        ok = bool(sig) and key.verify(blob, sig)
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

    if amount is not None:
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
