"""
Revoking an agent, across both rails.

An agent's authority does not live in one place, so switching it off is not one
action. It lives in three:

    the UPI block      stops future loads
    the card token     stops the card spending
    the float on card  is money already moved, and neither of the above touches it

The third is the one that gets forgotten. Load Rs 1,240 at 14:00, revoke at 14:05,
and the block is dead while the money sits on the card, perfectly spendable. A revoke
that only kills the block has not revoked anything the agent currently holds.

So `revoke` fans out to all three and reports each separately. A revoke that half
worked is worse than one that failed outright, because the user believes it worked.

The signed record it produces exists for a narrower reason. If a payment lands at
14:06 and the user says they revoked at 14:05, somebody eats that payment. Without a
signed, timestamped record it is the operator's log against the merchant's.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

import vcard
from consent import Keypair, canonical
from core import Money
from models import MandateStatus, iso, utcnow


# --------------------------------------------------------------------------
# Reasons
# --------------------------------------------------------------------------

REASONS = {
    "user_revoked": "the user switched the agent off",
    "expired": "the mandate reached its end date",
    "device_lost": "the appliance was lost, sold or reset",
    "suspected_compromise": "the agent behaved in a way that suggests it is not itself",
    "budget_exhausted": "nothing left to spend",
}


@dataclass
class RevocationRecord:
    """
    Signed proof that authority ended, and when.

    Signed by the operator -- the party that holds authority in this design. That is
    the honest signer: the user asked, but the operator is the one who can actually
    stop the agent, and therefore the one answerable if it did not stop.
    """

    agent_id: str
    reason: str
    at: Any
    steps: list[dict]
    signature: bytes = b""
    signer: str = ""

    def payload(self) -> dict[str, Any]:
        return {
            "type": "Revocation",
            "agent_id": self.agent_id,
            "reason": self.reason,
            "at": iso(self.at),
            "steps": self.steps,
        }

    def sign_with(self, key: Keypair) -> "RevocationRecord":
        self.signer = key.label
        self.signature = key.sign(canonical(self.payload()))
        return self

    def verify_with(self, key: Keypair) -> bool:
        return bool(self.signature) and key.verify(canonical(self.payload()), self.signature)

    @property
    def id(self) -> str:
        return sha256(canonical(self.payload())).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "id": self.id, "signer": self.signer,
                "complete": self.complete}

    @property
    def complete(self) -> bool:
        """True only if every step actually succeeded."""
        return all(s["ok"] for s in self.steps)


# --------------------------------------------------------------------------
# The fan-out
# --------------------------------------------------------------------------

def revoke(sim, card: vcard.VirtualCard, reason: str = "user_revoked",
           operator_key: Keypair | None = None) -> RevocationRecord:
    """
    Switch an agent off on both rails, and return whatever is already in flight.

    Steps run in this order deliberately. Kill the token first so nothing new can be
    spent while the rest runs; then stop future loads; then return the float. Doing
    the sweep first would leave a window where the card is empty but still live.
    """
    steps: list[dict] = []
    now = utcnow()

    # -- 1. kill the card token ------------------------------------------
    # in production this is an MDES call to the issuer. here the card's account is
    # frozen by pointing the card at a revoked state the spend path checks.
    try:
        sim.store.record_event("agent.token_killed", {
            "card_id": card.card_id, "agent_id": card.agent_id,
        })
        card.revoked = True
        steps.append({"step": "kill_card_token", "ok": True,
                      "detail": f"token for {card.agent_id} killed"})
    except Exception as exc:                                # noqa: BLE001
        steps.append({"step": "kill_card_token", "ok": False, "detail": str(exc)})

    # -- 2. stop future loads --------------------------------------------
    try:
        m = sim.store.get_mandate(card.umn)
        if m is None:
            steps.append({"step": "revoke_upi_block", "ok": False,
                          "detail": f"no mandate {card.umn}"})
        elif m.status is MandateStatus.REVOKED:
            steps.append({"step": "revoke_upi_block", "ok": True,
                          "detail": "already revoked"})
        else:
            m.status = MandateStatus.REVOKED
            sim.store.save_mandate(m)
            steps.append({"step": "revoke_upi_block", "ok": True,
                          "detail": f"{m.umn} revoked, "
                                    f"{m.remaining} of headroom released"})
    except Exception as exc:                                # noqa: BLE001
        steps.append({"step": "revoke_upi_block", "ok": False, "detail": str(exc)})

    # -- 3. return whatever is already on the card ------------------------
    try:
        left = vcard.balance(sim, card)
        if left.paise == 0:
            steps.append({"step": "sweep_float", "ok": True, "detail": "card was empty"})
        else:
            back = vcard.sweep(sim, card, f"revoke-{card.card_id}-{int(now.timestamp())}")
            ok = bool(back and back.ok)
            steps.append({
                "step": "sweep_float", "ok": ok,
                "detail": (f"returned {left}" if ok
                           else f"{left} still on the card -- sweep failed"),
            })
    except Exception as exc:                                # noqa: BLE001
        steps.append({"step": "sweep_float", "ok": False, "detail": str(exc)})

    rec = RevocationRecord(agent_id=card.agent_id, reason=reason, at=now, steps=steps)
    if operator_key is not None:
        rec.sign_with(operator_key)

    sim.store.record_event("agent.revoked", rec.to_dict())
    return rec


def is_revoked(card: vcard.VirtualCard) -> bool:
    return getattr(card, "revoked", False)
