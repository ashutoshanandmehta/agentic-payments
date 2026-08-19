"""
Signed mandates.

Three artifacts, following AP2's shape:

    IntentMandate   what the human authorised          signed by the principal
    CartMandate     what the agent actually selected   signed by the agent
    PaymentMandate  what the rail was asked to move    signed by the rail

The delta between the first two is decision drift. That is the whole point:
drift is only measurable because both ends are signed by *different* keys and
neither party can rewrite the other's half after the fact.

Signing is Ed25519. It is not HMAC on purpose -- a shared secret would let the
agent forge the principal's intent, which destroys the property being claimed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .intent import Intent, Money


# --------------------------------------------------------------------------
# Keys
# --------------------------------------------------------------------------

class Keypair:
    """An Ed25519 identity. Every actor in the simulation holds one."""

    def __init__(self, label: str, private: Ed25519PrivateKey | None = None) -> None:
        self.label = label
        self._private = private or Ed25519PrivateKey.generate()
        self.public: Ed25519PublicKey = self._private.public_key()

    def sign(self, payload: bytes) -> bytes:
        return self._private.sign(payload)

    def verify(self, payload: bytes, signature: bytes) -> bool:
        try:
            self.public.verify(signature, payload)
            return True
        except InvalidSignature:
            return False

    def __repr__(self) -> str:
        return f"Keypair({self.label})"


def canonical(payload: dict[str, Any]) -> bytes:
    """
    Deterministic serialisation. Two structurally identical payloads must produce
    byte-identical output, or signatures are meaningless.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def digest(payload: dict[str, Any]) -> str:
    return sha256(canonical(payload)).hexdigest()[:16]


# --------------------------------------------------------------------------
# Base
# --------------------------------------------------------------------------

@dataclass
class SignedMandate:
    """A payload plus a signature over its canonical form."""

    kind: str
    payload: dict[str, Any]
    signer: str
    signature: bytes = b""

    def sign_with(self, key: Keypair) -> "SignedMandate":
        self.signer = key.label
        self.signature = key.sign(canonical(self.payload))
        return self

    def verify_with(self, key: Keypair) -> bool:
        return bool(self.signature) and key.verify(canonical(self.payload), self.signature)

    @property
    def id(self) -> str:
        return digest(self.payload)

    def tamper(self, **changes: Any) -> "SignedMandate":
        """
        Mutate the payload *without* re-signing.

        Only used by adversarial scenarios. The signature must then fail to verify --
        if a test ever passes after calling this, the binding is broken.
        """
        p = dict(self.payload)
        p.update(changes)
        return SignedMandate(kind=self.kind, payload=p, signer=self.signer,
                             signature=self.signature)


# --------------------------------------------------------------------------
# The three mandates
# --------------------------------------------------------------------------

def intent_mandate(intent: Intent, principal: Keypair, agent_id: str,
                   nonce: str) -> SignedMandate:
    """Signed by the human. This is the authority; everything else is derived."""
    payload = {
        "type": "IntentMandate",
        "principal": principal.label,
        "agent": agent_id,
        "nonce": nonce,
        "constraints": intent.to_dict(),
    }
    return SignedMandate("IntentMandate", payload, principal.label).sign_with(principal)


@dataclass
class CartLine:
    merchant: str
    sku: str
    title: str
    quantity_amount: str
    quantity_unit: str
    unit_price_paise: int
    line_total_paise: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "merchant": self.merchant,
            "sku": self.sku,
            "title": self.title,
            "quantity": {"amount": self.quantity_amount, "unit": self.quantity_unit},
            "unit_price_paise": self.unit_price_paise,
            "line_total_paise": self.line_total_paise,
        }


def cart_mandate(lines: list[CartLine], agent: Keypair, intent_ref: str,
                 quoted_total: Money, charged_total: Money) -> SignedMandate:
    """
    Signed by the agent. Records what was actually selected.

    `quoted_total` and `charged_total` are kept separately on purpose: the gap
    between them is the quote-drift attack, and collapsing them into one field
    would make that attack unrepresentable.
    """
    payload = {
        "type": "CartMandate",
        "agent": agent.label,
        "intent_ref": intent_ref,
        "lines": [ln.to_dict() for ln in lines],
        "quoted_total_paise": quoted_total.paise,
        "charged_total_paise": charged_total.paise,
    }
    return SignedMandate("CartMandate", payload, agent.label).sign_with(agent)


def payment_mandate(cart_ref: str, intent_ref: str, amount: Money,
                    funding_principal: str, rail: Keypair) -> SignedMandate:
    """Signed by the rail once, and only once, both prior mandates verify."""
    payload = {
        "type": "PaymentMandate",
        "intent_ref": intent_ref,
        "cart_ref": cart_ref,
        "amount_paise": amount.paise,
        "funding_principal": funding_principal,
    }
    return SignedMandate("PaymentMandate", payload, rail.label).sign_with(rail)


# --------------------------------------------------------------------------
# Evidence bundle
# --------------------------------------------------------------------------

@dataclass
class Evidence:
    """
    What survives to a dispute.

    Assumption A14: a chargeback on an agent-initiated payment requires the intent,
    the cart, and the drift report. Without all three the merchant wins by default,
    because nobody can show what was authorised.
    """

    intent: SignedMandate
    cart: SignedMandate | None = None
    payment: SignedMandate | None = None
    drift: Any = None
    notes: list[str] = field(default_factory=list)

    def complete(self) -> bool:
        return all([self.intent, self.cart, self.payment, self.drift])
