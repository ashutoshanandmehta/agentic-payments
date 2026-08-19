"""
The shopping agent.

This agent is deliberately **naive and trusting**. It believes what merchants tell
it, it optimises on displayed unit price, and if a listing contains text that looks
like an instruction it may follow it.

That is not a flaw in the simulation, it is the design. The claim under test is that
safety comes from the mandate chain, not from the agent's good judgement -- so the
agent must be allowed to have bad judgement. An agent that defends itself proves
nothing, because a compromised agent will not defend itself.

Assumption A15: agent compromise is possible. Enforcement happens at the credential.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from ..market.merchant import Behaviour, Fulfilment, Listing, MerchantServer
from ..uap.intent import Intent, Money, Quantity, display_unit
from ..uap.mandate import CartLine, Keypair, SignedMandate, cart_mandate

#: crude detector for text that is trying to steer the agent
_INJECTION = re.compile(
    r"(ignore (all )?previous|system\s*:|disregard .*instruction|proceed to payment"
    r"|without further|approved a larger)", re.I
)


@dataclass
class Selection:
    merchant: MerchantServer
    listing: Listing
    packs: int
    fulfilment: Fulfilment


@dataclass
class Shopper:
    agent_id: str
    key: Keypair
    #: if True the agent notices and ignores injected instructions
    injection_aware: bool = False
    #: if True the agent shops outside the authorised seller set. models an agent
    #: that is buggy or compromised rather than a merchant that is hostile.
    ignore_allowlist: bool = False
    trace: list[str] = field(default_factory=list)

    # -- discovery -----------------------------------------------------------

    def discover(self, item: str, market: dict[str, MerchantServer],
                 allowed: frozenset[str]) -> list[tuple[MerchantServer, Listing]]:
        found: list[tuple[MerchantServer, Listing]] = []
        for name, server in market.items():
            if allowed and name not in allowed and not self.ignore_allowlist:
                continue
            for listing in server.search(item):
                found.append((server, listing))
                self.trace.append(
                    f"    saw {listing.merchant}/{listing.sku} at "
                    f"{listing.displayed_price} (claimed "
                    f"{Money(listing.displayed_unit_price_paise)}/"
                    f"{display_unit(listing.pack.base_unit)})"
                )
        return found

    # -- the part an attacker is aiming at -----------------------------------

    def _absorb(self, listings: list[tuple[MerchantServer, Listing]]) -> int:
        """
        Read merchant-supplied text. Returns a quantity multiplier.

        A merchant's blurb is untrusted input that lands directly in the agent's
        context. A naive agent acts on it.
        """
        multiplier = 1
        for _, l in listings:
            if l.blurb and _INJECTION.search(l.blurb):
                if self.injection_aware:
                    self.trace.append(
                        f"    [defended] ignored injected instruction in {l.sku}"
                    )
                else:
                    multiplier = 10
                    self.trace.append(
                        f"    [COMPROMISED] followed injected instruction in {l.sku} "
                        f"-> quantity x{multiplier}"
                    )
        return multiplier

    # -- selection -----------------------------------------------------------

    def select(self, intent: Intent,
               market: dict[str, MerchantServer]) -> Selection | None:
        listings = self.discover(intent.item, market, intent.allowed_merchants)
        if not listings:
            self.trace.append("    nothing found")
            return None

        multiplier = self._absorb(listings)

        # naive: trust the merchant's own claimed unit price
        server, listing = min(listings, key=lambda p: p[1].displayed_unit_price_paise)
        self.trace.append(
            f"    chose {listing.merchant}/{listing.sku} on claimed unit price"
        )

        want = intent.max_quantity.base_amount * multiplier
        packs = max(1, want // listing.pack.base_amount)

        fulfilment = server.checkout(listing, packs=packs)
        self.trace.append(
            f"    checkout -> {fulfilment.title} {fulfilment.pack} "
            f"charged {Money(fulfilment.line_total_paise)}"
        )
        return Selection(server, listing, packs, fulfilment)

    # -- mandate construction ------------------------------------------------

    def build_cart(self, sel: Selection, intent_ref: str) -> SignedMandate:
        f = sel.fulfilment
        line = CartLine(
            merchant=sel.merchant.name,
            sku=f.sku,
            title=f.title,
            quantity_amount=str(f.pack.amount),
            quantity_unit=f.pack.unit.value,
            unit_price_paise=f.unit_price_paise,
            line_total_paise=f.line_total_paise,
        )
        quoted = Money(sel.listing.displayed_price.paise * sel.packs)
        charged = Money(f.line_total_paise)
        return cart_mandate([line], self.key, intent_ref, quoted, charged)
