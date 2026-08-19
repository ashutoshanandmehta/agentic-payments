"""
Signed records.

Four things get signed at the payment boundary:

    authority    what the human allowed, in advance      signed by the human
    cart         what is being bought, and from whom     signed by -- see below
    request      the agent asking to pay                 signed by the agent
    settlement   the rail agreeing to move money         signed by the rail

**Who signs the cart is the open question of this thesis**, so it is a setting here
rather than a decision. `CartSigner` lets a scenario try each answer and see what the
system can still prove:

    AGENT     the agent can lie about what is in the cart
    MERCHANT  the shop can lie about the price
    BOTH      neither can lie alone, but the shop has to take part

Signing uses Ed25519, a public-key signature scheme. Each party holds a private key
nobody else has, so a signature proves who produced a record. This is not a shared
password: if the human and the agent shared one, the agent could forge the human's
authority and the whole argument collapses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .authority import Money, PaymentAuthority
from .cart import Cart, PaymentRequest


class CartSigner(str, Enum):
    AGENT = "agent"
    MERCHANT = "merchant"
    BOTH = "both"


class Keypair:
    """One party's cryptographic identity."""

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
    Turn a payload into bytes the same way every time.

    Without this, the same record could serialise two different ways and a valid
    signature would fail to verify.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def digest(payload: dict[str, Any]) -> str:
    return sha256(canonical(payload)).hexdigest()[:16]


@dataclass
class SignedRecord:
    """A payload plus one or more signatures over it."""

    kind: str
    payload: dict[str, Any]
    signatures: dict[str, bytes] = field(default_factory=dict)

    def sign_with(self, *keys: Keypair) -> "SignedRecord":
        blob = canonical(self.payload)
        for k in keys:
            self.signatures[k.label] = k.sign(blob)
        return self

    def verify_by(self, key: Keypair) -> bool:
        sig = self.signatures.get(key.label)
        return bool(sig) and key.verify(canonical(self.payload), sig)

    def signed_by(self) -> list[str]:
        return sorted(self.signatures)

    @property
    def id(self) -> str:
        return digest(self.payload)

    def tamper(self, **changes: Any) -> "SignedRecord":
        """
        Change the payload without re-signing.

        Only adversarial scenarios call this. Afterwards the signature must fail to
        verify -- if a test ever passes after a tamper, the binding is broken.
        """
        p = dict(self.payload)
        p.update(changes)
        return SignedRecord(kind=self.kind, payload=p, signatures=dict(self.signatures))


# --------------------------------------------------------------------------
# The four records
# --------------------------------------------------------------------------

def authority_record(authority: PaymentAuthority, principal: Keypair,
                     agent_id: str, nonce: str = "1") -> SignedRecord:
    payload = {
        "type": "PaymentAuthority",
        "principal": principal.label,
        "agent": agent_id,
        "nonce": nonce,
        "terms": authority.to_dict(),
    }
    return SignedRecord("PaymentAuthority", payload).sign_with(principal)


def cart_record(cart: Cart, signer: CartSigner,
                agent: Keypair, merchant: Keypair) -> SignedRecord:
    payload = {"type": "Cart", **cart.to_dict()}
    rec = SignedRecord("Cart", payload)
    if signer is CartSigner.AGENT:
        return rec.sign_with(agent)
    if signer is CartSigner.MERCHANT:
        return rec.sign_with(merchant)
    return rec.sign_with(agent, merchant)


def request_record(request: PaymentRequest, authority_ref: str,
                   agent: Keypair) -> SignedRecord:
    payload = {
        "type": "PaymentRequest",
        "authority_ref": authority_ref,
        **request.to_dict(),
    }
    return SignedRecord("PaymentRequest", payload).sign_with(agent)


def settlement_record(request_ref: str, cart_ref: str, authority_ref: str,
                      amount: Money, funding_principal: str,
                      rail: Keypair) -> SignedRecord:
    payload = {
        "type": "Settlement",
        "authority_ref": authority_ref,
        "cart_ref": cart_ref,
        "request_ref": request_ref,
        "amount_paise": amount.paise,
        "funding_principal": funding_principal,
    }
    return SignedRecord("Settlement", payload).sign_with(rail)


@dataclass
class Evidence:
    """
    What survives to a dispute.

    NPCI's dispute system (UDIR) has reason codes for failed, unauthorised and
    fraudulent payments. It has no code for "the agent misunderstood". This bundle is
    the proposal for what such a code would have to carry.
    """

    authority: SignedRecord
    cart: SignedRecord | None = None
    request: SignedRecord | None = None
    settlement: SignedRecord | None = None
    result: Any = None

    def complete(self) -> bool:
        return all([self.authority, self.cart, self.request, self.settlement, self.result])
