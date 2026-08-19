"""
The rail -- the only component that authorises.

Order of operations matters and is fixed:

    verify signatures  ->  evaluate drift  ->  resolve funding  ->  capture

Drift is evaluated *before* funding is resolved. A cart that violates its intent is
refused even when the money is available, because the question "can they afford it"
is not the question "were they allowed to buy it". Systems that check only the first
are spend caps, and a spend cap authorises a prompt-injected 10kg order for Rs 580
against a Rs 5,000 limit without blinking.

Nothing here trusts the agent. The agent's signature proves *which* agent acted; it
never proves the action was legitimate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .market.catalog import CATEGORIES
from .uap.delegation import Agent, Delegation
from .uap.drift import DriftReport, evaluate
from .uap.intent import Intent, Money
from .uap.ledger import Ledger, Reservation
from .uap.mandate import Evidence, Keypair, SignedMandate, payment_mandate


@dataclass
class Authorisation:
    approved: bool
    reason: str
    drift: DriftReport | None = None
    funding: Delegation | None = None
    payment: SignedMandate | None = None
    evidence: Evidence | None = None
    trace: list[str] = field(default_factory=list)


@dataclass
class Rail:
    key: Keypair
    ledger: Ledger

    def authorise(
        self,
        intent: Intent,
        intent_mandate: SignedMandate,
        cart_mandate: SignedMandate,
        principal_key: Keypair,
        agent: Agent,
        reservation: Reservation | None = None,
    ) -> Authorisation:
        trace: list[str] = []

        # -- 1. verify + drift ----------------------------------------------

        drift = evaluate(
            intent=intent,
            intent_mandate=intent_mandate,
            cart_mandate=cart_mandate,
            principal_key=principal_key,
            agent_key=agent.key,
            item_categories=CATEGORIES,
        )
        trace.append(f"drift evaluation: {drift.checks_run} checks, "
                     f"{len(drift.fatal)} fatal, score {drift.score:.2f}")

        evidence = Evidence(intent=intent_mandate, cart=cart_mandate, drift=drift)

        if not drift.authorised:
            return Authorisation(
                approved=False,
                reason=f"drift: {drift.fatal[0].kind}",
                drift=drift, evidence=evidence, trace=trace,
            )

        # -- 2. funding ------------------------------------------------------

        amount = Money(cart_mandate.payload["charged_total_paise"])
        category = CATEGORIES.get(intent.item, "unknown")
        funding, ftrace = agent.resolve_funding(category, amount)
        trace.extend(f"funding: {t}" for t in ftrace)

        if funding is None:
            return Authorisation(
                approved=False, reason="no delegation covers this purchase",
                drift=drift, evidence=evidence, trace=trace,
            )

        # -- 3. capture ------------------------------------------------------

        merchant = cart_mandate.payload["lines"][0]["merchant"]
        pm = payment_mandate(
            cart_ref=cart_mandate.id,
            intent_ref=intent_mandate.id,
            amount=amount,
            funding_principal=funding.principal.name,
            rail=self.key,
        )

        if reservation is not None:
            ok, why = reservation.capture(merchant, amount, pm.id)
            trace.append(f"reservation {reservation.reservation_id}: {why}")
            if not ok:
                return Authorisation(
                    approved=False, reason=f"reservation: {why}",
                    drift=drift, funding=funding, evidence=evidence, trace=trace,
                )

        funding.spent = funding.spent + amount
        evidence.payment = pm
        trace.append(f"authorised {amount} to {merchant} from {funding.principal.name}")

        return Authorisation(
            approved=True, reason="authorised", drift=drift, funding=funding,
            payment=pm, evidence=evidence, trace=trace,
        )
