"""
Where the check runs, and who is in a position to run it.

AP2 answers this by putting the binding check at the Merchant Payment Processor:
that party verifies the Payment Mandate against the hash of the Checkout JWT, and
verifies the closed cart against the constraints in the open mandate.

**UPI has no such party.** So the question the protocol answers by assumption is
open on this rail, and it is the question this module makes measurable.

## The two checks, and what they need to see

    Check A   does the payment request still match the cart?
              needs: the cart, and the payment request

    Check B   does the cart fit inside the authority?
              needs: the cart, and the authority

Both are arithmetic. Neither is hard. The difficulty is entirely about *who holds
which document at the moment the payment is authorised*.

## Seeing enough is not the same as being trusted

A party can fail to be the enforcer in two different ways, and they need keeping
apart because the fixes are different:

  * **Blind.** It cannot see one of the documents the check needs. This is fixable
    by adding a field to the rail.
  * **Conflicted.** It can see everything and still should not be trusted, because
    it is the party being constrained, or it profits from the check failing, or it
    runs inside the environment the agent controls. Adding fields does not fix this.

The merchant is the clearest case: it holds the cart, so it can run Check A
perfectly well, and its revenue is the number under dispute. A party that gains
from an inflated basket is not the party you ask whether the basket is inflated.

## What this module is for

`report()` runs both checks against every party twice: once on UPI as it is, and
once on a UPI that carries a cart reference. The difference between the two is the
proposal, stated as a table rather than an argument.

`UNVERIFIED`: which parties see what is modelled from the payment topology in
`rails.py` and the brief's Section II. It has not been checked against NPCI's
message specifications, and OC 228 has not been read.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class Evidence(enum.StrEnum):
    """The four documents a delegated payment produces."""

    AUTHORITY = "authority"              # what the human signed in advance
    CART = "cart"                        # what is being bought, and from whom
    PAYMENT_REQUEST = "payment_request"  # the agent asking to move money
    SETTLEMENT = "settlement"            # the rail agreeing that it moved


class Check(enum.StrEnum):
    A = "A"      # the payment request still matches the cart
    B = "B"      # the cart fits inside the authority


CHECK_NEEDS: dict[Check, set[Evidence]] = {
    Check.A: {Evidence.CART, Evidence.PAYMENT_REQUEST},
    Check.B: {Evidence.CART, Evidence.AUTHORITY},
}

CHECK_QUESTION: dict[Check, str] = {
    Check.A: "does the payment request still match the cart?",
    Check.B: "does the cart fit inside the authority?",
}


class Conflict(enum.StrEnum):
    """Why a party should not be trusted with the check, even if it can see enough."""

    NONE = "none"
    IS_CONSTRAINED = "is the party the check exists to constrain"
    GAINS_FROM_INFLATION = "earns more when the amount is higher"
    AGENT_CONTROLLED = "runs inside the environment the agent controls"


class Party(enum.StrEnum):
    AGENT = "agent"
    PAYER_PSP = "payer_psp"
    REMITTER_BANK = "remitter_bank"
    SWITCH = "switch"
    BENEFICIARY_BANK = "beneficiary_bank"
    MERCHANT = "merchant"
    MERCHANT_PROCESSOR = "merchant_processor"


@dataclass(frozen=True)
class PartyView:
    """One party: what it can see, whether it can be trusted, whether it exists here."""

    party: Party
    role: str
    sees: frozenset[Evidence]
    conflict: Conflict = Conflict.NONE
    #: AP2 leans on a party that has no equivalent in a UPI payment.
    exists_on_upi: bool = True

    @property
    def trusted(self) -> bool:
        return self.conflict is Conflict.NONE

    def can_see_enough_for(self, check: Check) -> bool:
        return CHECK_NEEDS[check] <= set(self.sees)

    def missing_for(self, check: Check) -> list[str]:
        return sorted(e.value for e in CHECK_NEEDS[check] - set(self.sees))

    def can_enforce(self, check: Check) -> bool:
        return self.exists_on_upi and self.trusted and self.can_see_enough_for(check)


# --------------------------------------------------------------------------
# UPI as it is today
# --------------------------------------------------------------------------

#: The agent has every document -- it assembled them. That is exactly why it cannot
#: be the enforcer, and `src/agent.py` already imports no rails so it cannot try.
UPI_TODAY: dict[Party, PartyView] = {
    Party.AGENT: PartyView(
        party=Party.AGENT,
        role="assembles the cart and asks to pay",
        sees=frozenset({Evidence.AUTHORITY, Evidence.CART, Evidence.PAYMENT_REQUEST}),
        conflict=Conflict.IS_CONSTRAINED,
    ),
    Party.PAYER_PSP: PartyView(
        party=Party.PAYER_PSP,
        role="the user's UPI app, which constructs the payment request",
        sees=frozenset({Evidence.CART, Evidence.PAYMENT_REQUEST}),
        conflict=Conflict.AGENT_CONTROLLED,
    ),
    Party.REMITTER_BANK: PartyView(
        party=Party.REMITTER_BANK,
        role="holds the user's account and the block or mandate against it",
        # It holds the authority and it debits the account. It has never seen a cart,
        # because UPI has no field that carries one.
        sees=frozenset({Evidence.AUTHORITY, Evidence.PAYMENT_REQUEST,
                        Evidence.SETTLEMENT}),
    ),
    Party.SWITCH: PartyView(
        party=Party.SWITCH,
        role="routes on the VPA handle and assigns the RRN",
        sees=frozenset({Evidence.PAYMENT_REQUEST, Evidence.SETTLEMENT}),
    ),
    Party.BENEFICIARY_BANK: PartyView(
        party=Party.BENEFICIARY_BANK,
        role="credits the merchant",
        sees=frozenset({Evidence.PAYMENT_REQUEST, Evidence.SETTLEMENT}),
    ),
    Party.MERCHANT: PartyView(
        party=Party.MERCHANT,
        role="issued the cart and receives the money",
        sees=frozenset({Evidence.CART, Evidence.PAYMENT_REQUEST, Evidence.SETTLEMENT}),
        conflict=Conflict.GAINS_FROM_INFLATION,
    ),
    Party.MERCHANT_PROCESSOR: PartyView(
        party=Party.MERCHANT_PROCESSOR,
        role="AP2 puts the binding check here",
        sees=frozenset({Evidence.CART, Evidence.PAYMENT_REQUEST, Evidence.SETTLEMENT}),
        exists_on_upi=False,
    ),
}


def with_cart_reference(
    base: dict[Party, PartyView] | None = None,
    to: Party = Party.REMITTER_BANK,
) -> dict[Party, PartyView]:
    """The proposal, as a one-line change: let the rail carry a cart reference.

    The remitter bank already holds the authority and already decides whether to
    debit. It is the only party in the path that is both disinterested and
    positioned to refuse. What it lacks is the cart -- so give it one.

    Returns a new topology; the original is left alone so both can be compared.
    """
    topology = dict(base or UPI_TODAY)
    view = topology[to]
    topology[to] = PartyView(
        party=view.party,
        role=view.role + ", plus a cart reference carried on the rail",
        sees=view.sees | {Evidence.CART},
        conflict=view.conflict,
        exists_on_upi=view.exists_on_upi,
    )
    return topology


# --------------------------------------------------------------------------
# The experiment
# --------------------------------------------------------------------------

@dataclass
class Finding:
    party: Party
    check: Check
    can_enforce: bool
    reason: str

    def to_dict(self) -> dict:
        return {
            "party": self.party.value,
            "check": self.check.value,
            "can_enforce": self.can_enforce,
            "reason": self.reason,
        }


def assess(view: PartyView, check: Check) -> Finding:
    """Can this party run this check, and if not, why not?

    Blindness and conflict are reported separately and blindness is reported first,
    because only one of them is fixable by changing the rail.
    """
    if not view.exists_on_upi:
        return Finding(view.party, check, False,
                       "no such party in a UPI payment")

    if not view.can_see_enough_for(check):
        missing = " and ".join(view.missing_for(check))
        return Finding(view.party, check, False,
                       f"blind: never sees the {missing}")

    if not view.trusted:
        return Finding(view.party, check, False,
                       f"conflicted: {view.conflict.value}")

    return Finding(view.party, check, True,
                   "sees both documents and has no stake in the amount")


def report(topology: dict[Party, PartyView] | None = None) -> dict:
    """Run both checks against every party."""
    topology = topology or UPI_TODAY
    findings = [assess(view, check)
                for check in Check
                for view in topology.values()]

    enforcers = {
        check.value: sorted(
            f.party.value for f in findings
            if f.check is check and f.can_enforce
        )
        for check in Check
    }

    return {
        "findings": [f.to_dict() for f in findings],
        "enforcers": enforcers,
        "unenforceable": sorted(c for c, who in enforcers.items() if not who),
    }


def who_can_enforce(check: Check,
                    topology: dict[Party, PartyView] | None = None) -> list[Party]:
    topology = topology or UPI_TODAY
    return [v.party for v in topology.values() if v.can_enforce(check)]
