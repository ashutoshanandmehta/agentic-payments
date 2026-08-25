"""
The card rail. A scoped token, validated by the network at every authorisation.

This is not the same shape as the UPI rail and the difference is the point of
spanning both.

## What a token is

Tokenisation replaces a card number with a network issued reference scoped to a
context. Apple Pay is the familiar example. The token is a reference and not a
bearer instrument. **It holds no value.** It de-tokenises inside the network back
to the real account.

An Agentic Token extends that. It carries an agent identifier and a scope object
holding spend caps, merchant categories and an expiry. The network validates that
scope at every single authorisation, not once at issue.

## Why that changes the architecture

On UPI there is no token. The authority is a block on the owner's own account, and
the block names one merchant. An agent that does not know its merchant in advance
therefore has to be handed money it controls, which means a load leg, which means
float. Every cost `vcard.py` measures follows from that one forced move.

On cards none of that is needed. The token authorises directly against the owner's
account and the money moves once, from the owner to the merchant. There is no load.
There is no float. There is nothing to sweep and nothing to strand.

So the three costs in `vcard.py` are not costs of the card rail. They are costs of
funding an agent over UPI, which is the only way UPI can express the thing at all.

## Where enforcement sits

This is the sharper half. On UPI the switch carries no scope and no notion of what
was bought, so nobody in the path can check the order. Here the network holds the
scope and checks it before it authorises. That is a real enforcement point and it
exists today.

It is also not free. Cards charge the merchant, and card acceptance in India is
narrower than UPI acceptance. The owner is choosing between an enforcement point
they can rely on and a rail that reaches everywhere.

`UNVERIFIED` The scope fields modelled here follow the Mastercard Agentic Token
description in the brief. They have not been checked against a network
specification, and no network validates anything in this simulator. What is modelled
is the shape and the placement of the check, not the network itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from core import Money, new_id, validate_vpa
from models import PaymentIntent, iso, utcnow


class TokenStatus:
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


# --------------------------------------------------------------------------
# The token
# --------------------------------------------------------------------------

@dataclass
class AgenticToken:
    """A network issued reference to the owner's card, scoped to one agent.

    It holds no balance. `funding_account` is the real card it resolves to inside
    the network, and the owner's money never leaves that account until a merchant
    is actually paid.
    """

    token_id: str
    agent_id: str
    owner_vpa: str
    funding_account: str

    #: the scope object the network validates at every authorisation
    per_txn_cap: Money
    total_cap: Money
    allowed_merchants: list[str]
    allowed_categories: list[str]
    expires_at: datetime

    consumed: Money = field(default_factory=Money.zero)
    status: str = TokenStatus.ACTIVE

    @property
    def remaining(self) -> Money:
        return self.total_cap - self.consumed

    @property
    def holds_value(self) -> bool:
        """Always false. A token is a reference and not a purse.

        Stated as a property because it is the thing that separates this rail from
        the UPI one, and a reader should be able to assert it rather than trust a
        docstring.
        """
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "token_id": self.token_id,
            "agent_id": self.agent_id,
            "owner_vpa": self.owner_vpa,
            "funding_account": self.funding_account,
            "per_txn_cap": self.per_txn_cap.to_rupees_str(),
            "total_cap": self.total_cap.to_rupees_str(),
            "consumed": self.consumed.to_rupees_str(),
            "remaining": self.remaining.to_rupees_str(),
            "allowed_merchants": self.allowed_merchants,
            "allowed_categories": self.allowed_categories,
            "expires_at": iso(self.expires_at),
            "status": self.status,
            "holds_value": self.holds_value,
        }


def issue(sim, agent_id: str, owner_vpa: str, funding_account: str,
          per_txn_cap: Money, total_cap: Money,
          allowed_merchants: list[str] | None = None,
          allowed_categories: list[str] | None = None,
          valid_for: timedelta = timedelta(days=90)) -> AgenticToken:
    """Issue a scoped token against the owner's card.

    Nothing moves. No account is created. The token is a reference, so issuing one
    has no effect on any balance anywhere.
    """
    if sim.store.get_account_by_vpa_safe(funding_account) is None:
        raise ValueError(f"no card account for {funding_account}")

    token = AgenticToken(
        token_id=new_id("tok"),
        agent_id=agent_id,
        owner_vpa=validate_vpa(owner_vpa),
        funding_account=validate_vpa(funding_account),
        per_txn_cap=per_txn_cap,
        total_cap=total_cap,
        allowed_merchants=[validate_vpa(m) for m in (allowed_merchants or [])],
        allowed_categories=list(allowed_categories or []),
        expires_at=utcnow() + valid_for,
    )
    sim.store.record_event("token.issued", token.to_dict())
    return token


# --------------------------------------------------------------------------
# What the network checks before it authorises
# --------------------------------------------------------------------------

def _check(name: str, passed: bool, detail: str) -> dict:
    return {"check": name, "passed": passed, "detail": detail}


def validate_scope(token: AgenticToken, merchant_vpa: str, amount: Money,
                   category: str | None = None,
                   now: datetime | None = None) -> tuple[bool, list[str], list[dict]]:
    """The scope check the network runs at every authorisation.

    This is the part UPI has no equivalent for. It runs before any money moves and
    it runs on every single authorisation rather than once when the token was
    issued.
    """
    now = now or utcnow()
    reasons: list[str] = []
    checks: list[dict] = []

    live = token.status == TokenStatus.ACTIVE
    checks.append(_check("token_active", live, f"status {token.status}"))
    if not live:
        reasons.append(f"the token is {token.status.lower()}")

    in_date = now <= token.expires_at
    checks.append(_check("token_in_date", in_date,
                         f"expires {token.expires_at.date()}"))
    if not in_date:
        reasons.append("the token has expired")

    merchant = validate_vpa(merchant_vpa)
    scoped = (not token.allowed_merchants) or merchant in token.allowed_merchants
    checks.append(_check("merchant_in_scope", scoped,
                         f"{merchant} against {token.allowed_merchants or 'any'}"))
    if not scoped:
        reasons.append(
            f"{merchant} is outside the merchants this token is scoped to"
        )

    if token.allowed_categories:
        in_cat = category is not None and category in token.allowed_categories
        checks.append(_check("category_in_scope", in_cat,
                             f"{category!r} against {token.allowed_categories}"))
        if not in_cat:
            reasons.append(
                f"{category!r} is outside the categories this token is scoped to"
            )

    under_txn = amount <= token.per_txn_cap
    checks.append(_check("under_token_txn_cap", under_txn,
                         f"{amount} against {token.per_txn_cap}"))
    if not under_txn:
        reasons.append(
            f"{amount} is over the {token.per_txn_cap} per payment cap on this token"
        )

    under_total = amount <= token.remaining
    checks.append(_check("within_token_total", under_total,
                         f"{amount} against {token.remaining} remaining"))
    if not under_total:
        reasons.append(
            f"{amount} is over the {token.remaining} left on this token"
        )

    return not reasons, reasons, checks


# --------------------------------------------------------------------------
# Paying
# --------------------------------------------------------------------------

def authorise(sim, token: AgenticToken, merchant_vpa: str, amount: Money,
              idempotency_key: str, order=None, quantity: str | None = None):
    """Pay a merchant against the token. One movement, owner to merchant.

    The network checks the scope first. If it passes, the token de-tokenises to the
    funding account and the money goes straight to the merchant. It never rests
    anywhere the agent controls, which is why this rail has no float to strand and
    no chain to sever.
    """
    ok, reasons, checks = validate_scope(
        token, merchant_vpa, amount,
        category=getattr(order, "category", None),
    )
    if not ok:
        from policy import Verdict
        verdict = Verdict(False, "SIM-TOKEN", reasons, checks)
        sim.store.record_event("token.refused", {
            "token_id": token.token_id, "merchant": merchant_vpa,
            "amount_paise": amount.paise, "reasons": reasons,
        })
        from orchestrator import PaymentResult
        return PaymentResult(None, verdict, None, trace=[
            {"step": "network scope check", "detail": "; ".join(reasons)},
        ])

    # On this rail the token is the authority. There is no UPI mandate and asking
    # for one would be asking the wrong rail's question. The scope check above is
    # what stands in its place, and unlike a mandate the network runs it on every
    # authorisation rather than trusting a limit set once.
    from orchestrator import Orchestrator
    from policy import PolicyConfig, PolicyEngine

    card_rail = Orchestrator(
        sim.store, sim.switch,
        PolicyEngine(
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
            resolver=sim.resolver, agent_name=sim.agent_name,
            order_signer=sim.policy.order_signer,
        ),
    )

    intent = PaymentIntent(
        should_pay=True, payee_vpa=validate_vpa(merchant_vpa), amount=amount,
        reason=f"token authorisation for {token.agent_id}",
        confidence=0.95, source="token",
    )
    result = card_rail.execute(
        intent=intent, payer_vpa=token.funding_account,
        idempotency_key=idempotency_key, umn=None,
        note=f"agentic token {token.token_id}", order=order,
        agent_id=token.agent_id, quantity=quantity,
    )

    if result.ok:
        token.consumed = token.consumed + amount
        sim.store.record_event("token.authorised", {
            "token_id": token.token_id, "txn_id": result.txn.txn_id,
            "amount_paise": amount.paise, "merchant": merchant_vpa,
        })
    return result


def revoke(sim, token: AgenticToken) -> AgenticToken:
    """Kill the token.

    One action and it is done. There is no float to return, because the token never
    held any. Compare `revocation.revoke`, which has to fan out to three places on
    the UPI funded path and where the float is the one that gets forgotten.
    """
    token.status = TokenStatus.REVOKED
    sim.store.record_event("token.revoked", {
        "token_id": token.token_id, "agent_id": token.agent_id,
    })
    return token


def float_held(sim, token: AgenticToken) -> Money:
    """Always zero. Kept as a function so a test can assert it rather than assume."""
    return Money.zero()
