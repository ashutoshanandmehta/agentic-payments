"""
The cross rail receipt.

This is the second half of the question the project asks. The gates answer whether
an agent was allowed to pay. This answers whether you can prove it afterwards.

## Why it has to exist

A card funded payment is two transactions on two rails. The user's money moves to
the card on UPI. The card then pays the merchant. Those are separate records with
separate references, and the load names the card and never the merchant.

So the ledger cannot reconstruct who bought what from whom. `vcard.trace` says so
in as many words. It reports that the rails prove load and spend are unrelated
transactions, and that the link exists only because the application kept it.

An application note is not evidence. In a dispute it is the operator's log against
the merchant's log. A receipt is the artifact that survives that argument, because
anybody can check it and nobody had to be trusted to keep it.

## What it binds

Five things, in one signed record.

* the registration, which says this agent acts for this owner
* the authority, which says what the owner allowed
* the order, which says what was being bought
* every leg of money that moved, on whichever rail it moved
* the outcome

## What verification actually proves

`verify` runs on public keys only. It never holds a secret belonging to any party
it is checking, which is the whole reason the artifact is worth anything to a third
party. It establishes four things.

1. The receipt is intact and was issued by the party it names.
2. The agent was registered to that owner and was not revoked.
3. The order carries the signatures it claims.
4. The money adds up. What left the user reached the merchant or came back.

Point 4 is the one the rails cannot do on their own.

## What it does not prove

It does not prove the order was true. A signature establishes authorship and not
honesty, and this project already measured that. The protection against an inflated
order is the ceiling on the authority. The receipt records what happened. It does
not make what happened correct.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

from consent import Order, canonical
from core import Money, new_id
from identity import Resolver, Signer, jws_sign, jws_verify
from models import iso, utcnow

#: schema version, following the convention in registration.py
RECEIPT_VCT = "payment.receipt.1"


class Rail:
    UPI = "upi"
    CARD = "card"


class Outcome:
    """How the payment ended.

    A receipt records what happened. A purchase that was refunded is a real
    outcome and its receipt has to verify, otherwise the only provable payments
    are the successful ones and a dispute has nothing to work with.
    """

    SETTLED = "settled"          # the merchant was paid
    RETURNED = "returned"        # nothing was bought and the money came back
    STRANDED = "float on card"   # money left the user and is sitting on the credential


class LegKind:
    """What a movement of money was for."""

    LOAD = "load"        # the user funds the agent credential
    SPEND = "spend"      # the credential pays the merchant
    DIRECT = "direct"    # the user pays the merchant, no credential in between
    SWEEP = "sweep"      # unspent float returns to the user
    REVERSAL = "reversal"


def _check(name: str, passed: bool, detail: str) -> dict:
    return {"check": name, "passed": passed, "detail": detail}


# --------------------------------------------------------------------------
# One movement of money
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Leg:
    """One transaction on one rail, recorded as it settled."""

    kind: str
    rail: str
    txn_id: str
    payer: str
    payee: str
    amount: Money
    state: str
    rrn: str | None = None

    @property
    def settled(self) -> bool:
        return self.state == "SETTLED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "rail": self.rail,
            "txn_id": self.txn_id,
            "payer": self.payer,
            "payee": self.payee,
            "amount_paise": self.amount.paise,
            "state": self.state,
            "rrn": self.rrn,
        }


# --------------------------------------------------------------------------
# The receipt
# --------------------------------------------------------------------------

@dataclass
class CrossRailReceipt:
    """One signed record of an authorised payment, across however many rails it took."""

    receipt_id: str
    agent_id: str
    owner_vpa: str
    registration_token: str
    umn: str | None
    order: Order
    legs: tuple[Leg, ...]
    outcome: str
    issued_at: Any = field(default_factory=utcnow)
    token: str = ""
    signer: str = ""

    # -- the signed content ------------------------------------------------

    def payload(self) -> dict[str, Any]:
        """Everything the signature covers.

        The order goes in as its own payload rather than as a summary. A summary
        would let the receipt agree with itself while disagreeing with the order
        the merchant holds.
        """
        return {
            "vct": RECEIPT_VCT,
            "receipt_id": self.receipt_id,
            "agent_id": self.agent_id,
            "owner_vpa": self.owner_vpa,
            "registration": self.registration_token,
            "umn": self.umn,
            "order": self.order.payload(),
            "order_signed_by": sorted(self.order.signatures),
            "legs": [leg.to_dict() for leg in self.legs],
            "outcome": self.outcome,
            "issued_at": iso(self.issued_at),
        }

    @property
    def id(self) -> str:
        return sha256(canonical(self.payload())).hexdigest()[:16]

    def sign_with(self, key: Signer) -> "CrossRailReceipt":
        self.signer = key.label
        self.token = jws_sign(self.payload(), key)
        return self

    # -- money ------------------------------------------------------------

    def legs_of(self, kind: str) -> list[Leg]:
        return [l for l in self.legs if l.kind == kind and l.settled]

    @property
    def left_the_user(self) -> Money:
        out = sum(l.amount.paise for l in self.legs_of(LegKind.LOAD))
        out += sum(l.amount.paise for l in self.legs_of(LegKind.DIRECT))
        return Money(out)

    @property
    def reached_the_merchant(self) -> Money:
        out = sum(l.amount.paise for l in self.legs_of(LegKind.SPEND))
        out += sum(l.amount.paise for l in self.legs_of(LegKind.DIRECT))
        return Money(out)

    @property
    def came_back(self) -> Money:
        out = sum(l.amount.paise for l in self.legs_of(LegKind.SWEEP))
        out += sum(l.amount.paise for l in self.legs_of(LegKind.REVERSAL))
        return Money(out)

    @property
    def unaccounted(self) -> Money:
        """Money that left the user and neither arrived nor returned.

        On a direct payment this is always zero. On a card funded payment it is
        float sitting on the credential, which is the failure `vcard.py` measures
        and the reconciliation sweep cannot see.
        """
        return self.left_the_user - self.reached_the_merchant - self.came_back

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.payload(),
            "id": self.id,
            "signer": self.signer,
            "left_the_user": self.left_the_user.to_rupees_str(),
            "reached_the_merchant": self.reached_the_merchant.to_rupees_str(),
            "came_back": self.came_back.to_rupees_str(),
            "unaccounted": self.unaccounted.to_rupees_str(),
        }


# --------------------------------------------------------------------------
# Verifying
# --------------------------------------------------------------------------

def verify(
    receipt: CrossRailReceipt,
    resolver: Resolver,
    registry=None,
    quantity: str | None = None,
) -> tuple[bool, list[str], list[dict]]:
    """Check a receipt the way a third party would.

    Public keys only. Pass the registry to have the agent's revocation status
    checked as well. Returns `(ok, reasons, checks)` to match the order gate.
    """
    reasons: list[str] = []
    checks: list[dict] = []

    # -- 1. the receipt itself --------------------------------------------

    out = jws_verify(receipt.token, resolver) if receipt.token else None
    intact = out is not None
    checks.append(_check("receipt_signed", intact,
                         f"issued by {receipt.signer or 'nobody'}"))
    if not intact:
        reasons.append("the receipt does not verify against any known issuer")
        return False, reasons, checks

    claims, _kid = out
    unaltered = claims == receipt.payload()
    checks.append(_check("receipt_unaltered", unaltered,
                         "signed content matches the record"))
    if not unaltered:
        reasons.append("the receipt was altered after it was signed")
        return False, reasons, checks

    # -- 2. the agent was registered and is still allowed to act -----------

    if registry is not None:
        ok_reg, reg_why, reg_claims = registry.verify(receipt.registration_token)
        checks.append(_check("agent_registered", ok_reg,
                             "; ".join(reg_why) if reg_why else receipt.agent_id))
        if not ok_reg:
            reasons.extend(reg_why)
        else:
            same_agent = reg_claims.get("agent_id") == receipt.agent_id
            checks.append(_check("registration_names_this_agent", same_agent,
                                 f"{reg_claims.get('agent_id')} against "
                                 f"{receipt.agent_id}"))
            if not same_agent:
                reasons.append(
                    "the registration in this receipt is for a different agent"
                )

    # -- 3. the order carries the signatures it claims ---------------------

    blob = canonical(receipt.order.payload())
    for name, sig in receipt.order.signatures.items():
        good = resolver.verify(name, blob, sig)
        checks.append(_check(f"order_signature_{name}", good, name))
        if not good:
            reasons.append(f"the order signature from {name} does not verify")

    # -- 4. the money adds up ---------------------------------------------
    # This is the part the rails cannot do. Each leg is a separate record with
    # its own reference, and nothing in either ledger relates them.

    order_total = receipt.order.total
    if receipt.order.is_metered and quantity is not None:
        order_total = receipt.order.tariff.expected(quantity)

    to_merchant = receipt.reached_the_merchant

    if receipt.outcome == Outcome.SETTLED:
        matches_order = to_merchant == order_total
        checks.append(_check("merchant_received_the_order_amount", matches_order,
                             f"{to_merchant} reached the merchant against an order "
                             f"of {order_total}"))
        if not matches_order:
            reasons.append(
                f"{to_merchant} reached the merchant but the order was {order_total}"
            )

        funded = receipt.left_the_user >= to_merchant
        checks.append(_check("enough_was_funded", funded,
                             f"{receipt.left_the_user} left the user for "
                             f"{to_merchant} of spending"))
        if not funded:
            reasons.append(
                f"only {receipt.left_the_user} left the user but {to_merchant} "
                f"reached the merchant"
            )
    else:
        # Nothing was bought. The claim being made is that the money came home,
        # so that is what gets checked.
        nothing_spent = to_merchant == Money.zero()
        checks.append(_check("merchant_received_nothing", nothing_spent,
                             f"{to_merchant} reached the merchant on a "
                             f"{receipt.outcome} receipt"))
        if not nothing_spent:
            reasons.append(
                f"this receipt says {receipt.outcome} but {to_merchant} reached "
                f"the merchant"
            )

        returned = receipt.came_back == receipt.left_the_user
        checks.append(_check("money_came_back", returned,
                             f"{receipt.came_back} returned of "
                             f"{receipt.left_the_user} that left"))
        if not returned:
            reasons.append(
                f"{receipt.left_the_user} left the user and only "
                f"{receipt.came_back} came back"
            )

    balanced = receipt.unaccounted == Money.zero()
    checks.append(_check("nothing_unaccounted", balanced,
                         f"{receipt.unaccounted} left the user and neither "
                         f"arrived nor returned"))
    if not balanced:
        reasons.append(
            f"{receipt.unaccounted} is unaccounted for. it left the user and "
            f"did not reach the merchant or come back"
        )

    # -- 5. the legs actually chain ---------------------------------------
    # The severed audit chain, closed. A spend has to start from the credential
    # a load funded, or the two are unrelated transactions after all.

    for spend in receipt.legs_of(LegKind.SPEND):
        funded_by = [l for l in receipt.legs_of(LegKind.LOAD)
                     if l.payee == spend.payer]
        chained = bool(funded_by)
        checks.append(_check(f"spend_chains_to_a_load_{spend.txn_id}", chained,
                             f"{spend.payer} was funded by "
                             f"{funded_by[0].txn_id if funded_by else 'nothing in this receipt'}"))
        if not chained:
            reasons.append(
                f"the spend from {spend.payer} has no load funding it in this "
                f"receipt, so the chain is broken"
            )

    return not reasons, reasons, checks


# --------------------------------------------------------------------------
# Building one from what actually happened
# --------------------------------------------------------------------------

def _leg(store, txn_id: str, kind: str, rail: str) -> Leg | None:
    txn = store.get_txn(txn_id)
    if txn is None:
        return None
    return Leg(kind=kind, rail=rail, txn_id=txn.txn_id, payer=txn.payer_vpa,
               payee=txn.payee_vpa, amount=txn.amount, state=txn.state.value,
               rrn=txn.rrn)


def for_direct(sim, order: Order, txn_id: str, agent_id: str,
               umn: str | None = None) -> CrossRailReceipt:
    """A receipt for a payment that never touched a credential."""
    leg = _leg(sim.store, txn_id, LegKind.DIRECT, Rail.UPI)
    legs = tuple(l for l in (leg,) if l is not None)
    reg = sim.store.get_registration(agent_id) or {}
    return CrossRailReceipt(
        receipt_id=new_id("rcpt"), agent_id=agent_id,
        owner_vpa=reg.get("owner_vpa", ""),
        registration_token=reg.get("token", ""),
        umn=umn, order=order, legs=legs,
        outcome=(Outcome.SETTLED if legs and legs[0].settled
                 else Outcome.RETURNED),
    )


def for_card(sim, card, order: Order, load_txn_id: str,
             spend_txn_id: str | None = None,
             sweep_txn_id: str | None = None) -> CrossRailReceipt:
    """A receipt for a card funded payment, spanning both rails.

    The load is on UPI and the spend is on the card rail. Recording them together
    is the point. Apart, they are two unrelated transactions.
    """
    # The spend is always on the card, because the card is the only instrument the
    # agent pays with. The load could have come from either rail, so the receipt
    # records which one rather than assuming.
    funded_by = card.funding.get(load_txn_id, Rail.UPI)

    legs = []
    for txn_id, kind, rail in (
        (load_txn_id, LegKind.LOAD, funded_by),
        (spend_txn_id, LegKind.SPEND, Rail.CARD),
        (sweep_txn_id, LegKind.SWEEP, funded_by),
    ):
        if txn_id:
            leg = _leg(sim.store, txn_id, kind, rail)
            if leg is not None:
                legs.append(leg)

    reg = sim.store.get_registration(card.agent_id) or {}
    spent = any(l.kind == LegKind.SPEND and l.settled for l in legs)
    swept = any(l.kind == LegKind.SWEEP and l.settled for l in legs)

    return CrossRailReceipt(
        receipt_id=new_id("rcpt"), agent_id=card.agent_id,
        owner_vpa=reg.get("owner_vpa", card.owner_vpa),
        registration_token=reg.get("token", ""),
        umn=card.umn, order=order, legs=tuple(legs),
        outcome=(Outcome.SETTLED if spent
                 else Outcome.RETURNED if swept
                 else Outcome.STRANDED),
    )
