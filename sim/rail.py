"""
The rail. The only thing here that can approve a payment.

The order is fixed and it matters:

    check the records  ->  decide whose money  ->  move it

The rules are checked before the money is looked at. "Can they afford it" is not the
same question as "were they allowed to buy it", and a system that only asks the first
is a spending limit. A spending limit approves a Rs 5,400 payment against a Rs 540
cart without complaint, because Rs 5,400 is under the Rs 10,000 block.

Nothing here trusts the agent. The agent's signature proves which agent asked. It
never proves the asking was legitimate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .uap.authority import Money, PaymentAuthority
from .uap.check import CheckResult, check
from .uap.delegation import Agent, Delegation
from .uap.mandate import (
    CartSigner,
    Evidence,
    Keypair,
    SignedRecord,
    settlement_record,
)


@dataclass
class Outcome:
    approved: bool
    reason: str
    result: CheckResult | None = None
    funding: Delegation | None = None
    settlement: SignedRecord | None = None
    evidence: Evidence | None = None
    trace: list[str] = field(default_factory=list)


@dataclass
class Rail:
    key: Keypair
    cart_signer: CartSigner = CartSigner.AGENT
    #: running state per authority id
    spent: dict[str, Money] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    nonces: dict[str, set[str]] = field(default_factory=dict)

    def authorise(
        self,
        authority: PaymentAuthority,
        authority_rec: SignedRecord,
        cart_rec: SignedRecord,
        request_rec: SignedRecord,
        principal_key: Keypair,
        agent: Agent,
        merchant_key: Keypair,
        now: int,
    ) -> Outcome:
        trace: list[str] = []
        aid = authority_rec.id

        result = check(
            authority=authority,
            authority_rec=authority_rec,
            cart_rec=cart_rec,
            request_rec=request_rec,
            principal_key=principal_key,
            agent_key=agent.key,
            merchant_key=merchant_key,
            cart_signer=self.cart_signer,
            now=now,
            spent_so_far=self.spent.get(aid, Money(0)),
            payments_so_far=self.counts.get(aid, 0),
            seen_nonces=self.nonces.get(aid, set()),
        )
        trace.append(f"{result.checks_run} checks run, {len(result.fatal)} failed, "
                     f"score {result.score:.2f}")

        evidence = Evidence(authority=authority_rec, cart=cart_rec,
                            request=request_rec, result=result)

        if not result.passed:
            return Outcome(False, f"refused: {result.fatal[0].kind}",
                           result, evidence=evidence, trace=trace)

        # -- whose money? ---------------------------------------------------

        amount = Money(request_rec.payload["amount_paise"])
        category = cart_rec.payload["category"]
        funding, ftrace = agent.resolve_funding(category, amount)
        trace.extend(f"funding: {t}" for t in ftrace)

        if funding is None:
            return Outcome(False, "no delegation covers this payment",
                           result, evidence=evidence, trace=trace)

        # -- move it --------------------------------------------------------

        st = settlement_record(
            request_ref=request_rec.id, cart_ref=cart_rec.payload["cart_id"],
            authority_ref=aid, amount=amount,
            funding_principal=funding.principal.name, rail=self.key,
        )
        funding.spent = funding.spent + amount
        self.spent[aid] = self.spent.get(aid, Money(0)) + amount
        self.counts[aid] = self.counts.get(aid, 0) + 1
        self.nonces.setdefault(aid, set()).add(request_rec.payload["nonce"])

        evidence.settlement = st
        trace.append(f"paid {amount} to {request_rec.payload['merchant']} "
                     f"from {funding.principal.name}")

        return Outcome(True, "approved", result, funding, st, evidence, trace)
