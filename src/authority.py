"""
What the human allowed, and which rail can actually carry it.

The brief contradicts itself here, and this module is where the contradiction gets
resolved rather than papered over. Section IV says the authority "is recorded as a
ReservePay block on UPI". Section II-B says a ReservePay block names one merchant.
The whole problem is that the agent does not know the merchant when the authority
is created. All three cannot be true at once.

The resolution is not to pick one. It is to keep the authority abstract -- who may
spend, how much, on what, until when -- and then ask each rail whether it can
express that. **None of them can express all of it.** That is the finding, and it
is the argument for an authorisation layer sitting above the rails.

## What each rail loses

    upi_reservepay   funds blocked against ONE named merchant.
                     A multi-merchant authority is not expressible at all.

    upi_circle       delegation attached to a DEVICE, not a payee.
                     Expresses a spending cap. Carries no merchant scope and no
                     category scope, so "groceries only, these three shops" degrades
                     to "this device, up to this much, anywhere".

    card_token       merchant and category scope survive at the network. But the
                     money rests on a credential the agent holds, and `vcard.py`
                     already measures what that costs: merchant scoping moves to the
                     card, float strands, and the audit chain is severed.

So the honest summary is that UPI's two primitives each drop something the user
actually said, and the card rail keeps the scope but moves the money to the agent.

## Who could enforce it

Worth stating here because it drives the rest of the design. AP2 puts the binding
check at the Merchant Payment Processor. UPI has no such party. See
`enforcement.py` for which parties on a UPI payment can see enough to run the
check, and which of them you would want to.

## A warning about the numbers below

Every figure in `RAIL_LIMITS` is `UNVERIFIED`. They come from the brief, which took
them from secondary sources. NPCI Operating Circular 228 and 201-B have not been
read. **Do not put these in a paper before checking them**, and note that the code
does not depend on the figures being right -- it depends on the *shape* of what
each rail can and cannot say, which is the part that is well attested.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from core import Money


class Rail(enum.StrEnum):
    """Where an authority is actually recorded."""

    UPI_RESERVEPAY = "upi_reservepay"
    UPI_CIRCLE = "upi_circle"
    CARD_TOKEN = "card_token"


@dataclass(frozen=True)
class RailLimits:
    """What one rail can express, and what it silently drops.

    `scope_*` flags are the load-bearing part. The money figures are the part that
    needs checking against the circulars.
    """

    rail: Rail
    description: str

    #: can the authority name which merchants may be paid?
    scopes_merchant: bool
    #: can it be limited to more than one merchant at a time?
    multi_merchant: bool
    #: can it say what may be bought, not just from whom?
    scopes_category: bool
    #: does the money stay in the user's account until it is spent?
    funds_stay_with_user: bool

    #: UNVERIFIED, from the brief's secondary sources
    max_block: Money | None = None
    max_validity_days: int | None = None
    source_note: str = ""


#: UNVERIFIED throughout. See the module docstring.
RAIL_LIMITS: dict[Rail, RailLimits] = {
    Rail.UPI_RESERVEPAY: RailLimits(
        rail=Rail.UPI_RESERVEPAY,
        description="funds blocked in the user's own account against one named merchant",
        scopes_merchant=True,
        multi_merchant=False,
        scopes_category=False,
        funds_stay_with_user=True,
        max_block=Money.rupees("10000"),
        max_validity_days=90,
        source_note="brief II-B, citing NPCI OC 228 of October 2025 - UNVERIFIED",
    ),
    Rail.UPI_CIRCLE: RailLimits(
        rail=Rail.UPI_CIRCLE,
        description="delegation attached to a device, with a spending cap and no payee scope",
        scopes_merchant=False,
        multi_merchant=True,          # vacuously: it cannot name any merchant at all
        scopes_category=False,
        funds_stay_with_user=True,
        max_block=Money.rupees("15000"),
        max_validity_days=None,
        source_note="brief II-B, citing NPCI OC 201-B of October 2025 - UNVERIFIED",
    ),
    Rail.CARD_TOKEN: RailLimits(
        rail=Rail.CARD_TOKEN,
        description="network-issued token with a scope object the network validates",
        scopes_merchant=True,
        multi_merchant=True,
        scopes_category=True,
        funds_stay_with_user=False,   # this is the whole cost of the card hop
        max_block=None,
        max_validity_days=None,
        source_note="Mastercard Agentic Tokens - shape only, not tested against a network",
    ),
}


# --------------------------------------------------------------------------
# Can this rail carry this authority?
# --------------------------------------------------------------------------

@dataclass
class Expressibility:
    """Whether a rail can carry an authority, and what it would drop if forced."""

    rail: Rail
    expressible: bool
    losses: list[str]

    def to_dict(self) -> dict:
        return {
            "rail": self.rail.value,
            "expressible": self.expressible,
            "losses": self.losses,
        }


def check_expressible(
    rail: Rail,
    allowed_payees: list[str],
    categories: list[str] | None = None,
    total_cap: Money | None = None,
) -> Expressibility:
    """Ask one rail whether it can say what the user actually said.

    Returns the losses rather than raising, because the losses *are* the result.
    A rail that can carry the authority reports no losses; one that cannot reports
    exactly which of the user's instructions it would have to discard.
    """
    limits = RAIL_LIMITS[rail]
    losses: list[str] = []
    categories = categories or []

    names_a_merchant = bool(allowed_payees) and allowed_payees != ["*"]
    names_several = len(allowed_payees) > 1 or allowed_payees == ["*"]

    if names_a_merchant and not limits.scopes_merchant:
        losses.append(
            f"{rail.value} attaches to a device, not a payee, so "
            f"'only {', '.join(allowed_payees)}' cannot be recorded -- the agent "
            f"could pay anyone"
        )

    if names_several and limits.scopes_merchant and not limits.multi_merchant:
        target = "any merchant" if allowed_payees == ["*"] else \
                 f"{len(allowed_payees)} merchants"
        losses.append(
            f"{rail.value} blocks funds against one named merchant, so an authority "
            f"for {target} is not expressible; the merchant must be known up front"
        )

    if categories and not limits.scopes_category:
        losses.append(
            f"{rail.value} carries no notion of what was bought, so "
            f"'{', '.join(categories)} only' cannot be recorded"
        )

    if not limits.funds_stay_with_user:
        losses.append(
            f"{rail.value} moves the money onto a credential the agent controls "
            f"before the merchant is paid -- see vcard.py for what that costs"
        )

    if (limits.max_block is not None and total_cap is not None
            and total_cap > limits.max_block):
        losses.append(
            f"{total_cap} exceeds the {limits.max_block} ceiling for {rail.value} "
            f"({limits.source_note})"
        )

    return Expressibility(rail=rail, expressible=not losses, losses=losses)


def compare_rails(
    allowed_payees: list[str],
    categories: list[str] | None = None,
    total_cap: Money | None = None,
) -> dict[Rail, Expressibility]:
    """Put the same authority to every rail. This is the experiment.

    If no rail comes back expressible, that is not a bug in the simulator. It is
    the gap the thesis is about: the user said something none of the available
    primitives can record.
    """
    return {
        rail: check_expressible(rail, allowed_payees, categories, total_cap)
        for rail in Rail
    }


def any_rail_carries(
    allowed_payees: list[str],
    categories: list[str] | None = None,
    total_cap: Money | None = None,
) -> bool:
    return any(
        e.expressible
        for e in compare_rails(allowed_payees, categories, total_cap).values()
    )
