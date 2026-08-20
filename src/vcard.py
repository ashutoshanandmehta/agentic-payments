"""
Agent virtual cards: money parks with the agent before it reaches the merchant.

The direct model is one payment. The user's funds move from their bank to the
merchant's bank, and the mandate governs that single movement.

This model is two payments with a stop in between:

    LOAD    user's bank  ->  the agent's card      governed by the user's mandate
    SPEND   the agent's card  ->  merchant's bank  governed by nothing the user signed

That second line is the whole thing worth studying. Once the money is on the card it
belongs to the card, and the user's mandate has already been satisfied and consumed.

Three consequences fall out of the structure, and the tests in
`tests/test_vcard.py` assert each of them rather than taking my word for it:

1.  **Merchant scoping stops working.** On the load, the payee is the *card*, not the
    shop -- so the mandate's `allowed_payees` has to name the card. A mandate can no
    longer say "only Brewhouse". It can only say "only this card", and the card can
    then pay anyone.

2.  **Float gets stranded.** If the load succeeds and the spend fails, the money is
    sitting on the card. It has left the user and not reached the merchant, and no
    reconciliation sweep looks there, because as far as the rails are concerned the
    load settled perfectly.

3.  **The audit chain is severed.** The load and the spend are separate transactions
    with separate references. Nothing in the ledger says this spend came from that
    load unless something outside the rails records the link.

In production this arrangement holds customer funds, which in India needs a PPI or PA
licence. That is a funding question, not a simulation question, and the simulation is
where you find out whether it is worth funding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from consent import Order
from core import Money, new_id, validate_vpa
from models import AccountType, PaymentIntent
from orchestrator import Orchestrator, PaymentResult
from policy import PolicyConfig, PolicyEngine


class CardRevoked(Exception):
    """Raised when a killed token is asked to spend."""


# --------------------------------------------------------------------------
# The card
# --------------------------------------------------------------------------

@dataclass
class VirtualCard:
    """
    A spending account the agent controls.

    It is addressed by a VPA because everything in this simulator is. A real virtual
    card would carry a PAN and run on card rails; the shape of the problem -- money
    resting somewhere the agent controls -- is identical either way.
    """

    card_id: str
    agent_id: str
    vpa: str
    owner_vpa: str
    umn: str
    #: load_txn_id -> the spends drawn against it. the link the rails do not keep.
    chain: dict[str, list[str]] = field(default_factory=dict)
    #: set by revocation.revoke(). a killed token spends nothing, even if funded.
    revoked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "agent_id": self.agent_id,
            "vpa": self.vpa,
            "owner_vpa": self.owner_vpa,
            "umn": self.umn,
            "chain": self.chain,
            "revoked": self.revoked,
        }


# --------------------------------------------------------------------------
# Issuing
# --------------------------------------------------------------------------

def issue(sim, agent_id: str, owner_vpa: str, umn: str,
          handle: str = "upisim") -> VirtualCard:
    """Create the card's account. Idempotent, so seeding twice is safe."""
    slug = agent_id.replace(":", "").replace("-", "").replace("_", "")[:14].lower()
    vpa = validate_vpa(f"vc{slug}@{handle}")

    existing = sim.store.get_account_by_vpa_safe(vpa)
    if existing is None:
        sim.store.create_account(
            vpa=vpa,
            holder_name=f"Virtual card for {agent_id}",
            account_type=AccountType.AGENT_CARD,
            opening_balance=Money(0),
        )
    return VirtualCard(
        card_id=new_id("vc"), agent_id=agent_id, vpa=vpa,
        owner_vpa=validate_vpa(owner_vpa), umn=umn,
    )


def balance(sim, card: VirtualCard) -> Money:
    acct = sim.store.get_account_by_vpa(card.vpa)
    return acct.balance


# --------------------------------------------------------------------------
# The two legs
# --------------------------------------------------------------------------

def load(sim, card: VirtualCard, amount: Money, idempotency_key: str,
         order: Order | None = None, confidence: float = 0.95) -> PaymentResult:
    """
    Leg one: move the user's money onto the card.

    Fully gated. The user's mandate governs this, exactly as it would a direct
    payment -- note that the payee it sees is the card, never the shop.
    """
    intent = PaymentIntent(
        should_pay=True, payee_vpa=card.vpa, amount=amount,
        reason=f"load virtual card for {card.agent_id}",
        confidence=confidence, source="vcard",
    )
    result = sim.orchestrator.execute(
        intent=intent, payer_vpa=card.owner_vpa, idempotency_key=idempotency_key,
        umn=card.umn, note=f"vcard load: {card.card_id}", order=order,
    )
    if result.ok:
        card.chain.setdefault(result.txn.txn_id, [])
        sim.store.record_event("vcard.load", {
            "card_id": card.card_id, "txn_id": result.txn.txn_id,
            "amount_paise": amount.paise,
        })
    return result


def spend(sim, card: VirtualCard, payee_vpa: str, amount: Money,
          idempotency_key: str, order: Order | None = None,
          load_txn_id: str | None = None) -> PaymentResult:
    """
    Leg two: the card pays the merchant.

    **The user's mandate does not govern this leg.** It was satisfied and consumed on
    the load; the money on the card is the card's. So this runs through a second
    policy engine with `require_mandate=False`, which is not a shortcut -- it is an
    honest statement of who is actually authorising the movement.

    Operator policy still applies, and so does the order gate if it is switched on.
    Those are the only protections left.
    """
    if card.revoked:
        raise CardRevoked(
            f"the token for {card.agent_id} was revoked; it cannot spend"
        )

    card_policy = PolicyEngine(
        sim.store,
        PolicyConfig(
            require_mandate=False,
            require_order=sim.policy.config.require_order,
            order_ttl_seconds=sim.policy.config.order_ttl_seconds,
            max_txn_amount=sim.policy.config.max_txn_amount,
            max_daily_total=sim.policy.config.max_daily_total,
            max_txns_per_hour=sim.policy.config.max_txns_per_hour,
            min_confidence=sim.policy.config.min_confidence,
        ),
        agent_key=sim.agent_key,
        merchant_keys=sim.merchant_keys,
        order_signer=sim.policy.order_signer,
    )
    card_rail = Orchestrator(sim.store, sim.switch, card_policy)

    intent = PaymentIntent(
        should_pay=True, payee_vpa=validate_vpa(payee_vpa), amount=amount,
        reason=f"card spend by {card.agent_id}", confidence=0.95, source="vcard",
    )
    result = card_rail.execute(
        intent=intent, payer_vpa=card.vpa, idempotency_key=idempotency_key,
        umn=None, note=f"vcard spend: {card.card_id}", order=order,
    )
    if result.ok and load_txn_id:
        card.chain.setdefault(load_txn_id, []).append(result.txn.txn_id)
        sim.store.record_event("vcard.spend", {
            "card_id": card.card_id, "load_txn_id": load_txn_id,
            "spend_txn_id": result.txn.txn_id, "amount_paise": amount.paise,
        })
    return result


def sweep(sim, card: VirtualCard, idempotency_key: str) -> PaymentResult | None:
    """
    Return whatever is left on the card to the user.

    Nothing in the rails does this on its own. The reconciliation sweep resolves
    payments stuck *between* two legs of one transaction; a funded card is not stuck,
    it is simply sitting there. Somebody has to decide to give it back.
    """
    left = balance(sim, card)
    if left.paise <= 0:
        return None

    # Returning the money is not enough on its own. The load consumed the user's
    # mandate headroom, and a purchase that never happened must not keep eating it --
    # otherwise a run of failures silently exhausts the cap while the user is made
    # whole in cash. Headroom is released for exactly the amount coming back.
    mandate = sim.store.get_mandate(card.umn) if card.umn else None
    if mandate is not None and mandate.consumed.paise >= left.paise:
        mandate.consumed = mandate.consumed - left
        sim.store.save_mandate(mandate)
        sim.store.record_event("vcard.headroom_released", {
            "card_id": card.card_id, "umn": card.umn, "amount_paise": left.paise,
        })

    card_policy = PolicyEngine(
        sim.store, PolicyConfig(require_mandate=False, require_order=False),
        agent_key=sim.agent_key, merchant_keys=sim.merchant_keys,
    )
    card_rail = Orchestrator(sim.store, sim.switch, card_policy)

    intent = PaymentIntent(
        should_pay=True, payee_vpa=card.owner_vpa, amount=left,
        reason="return unspent float", confidence=1.0, source="vcard",
    )
    return card_rail.execute(
        intent=intent, payer_vpa=card.vpa, idempotency_key=idempotency_key,
        umn=None, note=f"vcard sweep: {card.card_id}",
    )


# --------------------------------------------------------------------------
# What the audit can and cannot reconstruct
# --------------------------------------------------------------------------

def trace(sim, card: VirtualCard) -> dict[str, Any]:
    """
    Try to reconstruct user -> merchant from the ledger alone, and report the gap.

    `from_rails` is what the transaction records prove on their own. `from_app` is
    what the link table adds. The difference between them is the cost of the hop: in
    a dispute, only the first is evidence the rails will vouch for.
    """
    loads, spends = [], []
    for t in sim.store.list_txns(limit=500):
        if t.payee_vpa == card.vpa:
            loads.append(t)
        elif t.payer_vpa == card.vpa:
            spends.append(t)

    linked = {s for v in card.chain.values() for s in v}
    return {
        "card_vpa": card.vpa,
        "balance": balance(sim, card).to_rupees_str(),
        "loads": [{"txn_id": t.txn_id, "from": t.payer_vpa,
                   "amount": t.amount.to_rupees_str(), "state": t.state.value}
                  for t in loads],
        "spends": [{"txn_id": t.txn_id, "to": t.payee_vpa,
                    "amount": t.amount.to_rupees_str(), "state": t.state.value,
                    "linked_to_a_load": t.txn_id in linked}
                   for t in spends],
        # the rails know money arrived and money left. they do not know which load
        # funded which spend -- that link exists only because this module kept it.
        "from_rails": "load and spend are unrelated transactions",
        "from_app": f"{len(linked)} spend(s) linked to a load by the application",
    }
