"""Mandate validation and the deterministic policy gate.

This is the security boundary of the whole system. The agent proposes; this
module disposes. Nothing here calls a model, and nothing here is probabilistic
-- the same intent against the same state always produces the same verdict,
which is what makes an autonomous payer auditable.

Two layers, checked in order:

  1. **Mandate** -- the user's own pre-authorisation (UPI AutoPay-style):
     is it active, in date, is this payee in scope, is the amount under the
     per-transaction ceiling, is there headroom left in the total cap?
  2. **Policy** -- operator-side guardrails independent of any mandate:
     velocity limits, a global per-transaction ceiling, duplicate-payment
     suppression, and a confidence floor on the model's own output.

An agent with a valid mandate can still be blocked by policy. That ordering
is deliberate: the mandate is what the *user* permitted, policy is what the
*operator* permits, and neither alone is sufficient.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from core import Money, validate_vpa
from models import Mandate, MandateStatus, PaymentIntent, TxnState, utcnow
from consent import Order, OrderSigner, validate_order
from identity import Resolver
from store import Store


@dataclass
class Verdict:
    allowed: bool
    code: str                      # "00" when allowed, else a rejection code
    reasons: list[str] = field(default_factory=list)
    checks: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "code": self.code,
            "reasons": self.reasons,
            "checks": self.checks,
        }


def _check(name: str, passed: bool, detail: str) -> dict:
    return {"check": name, "passed": passed, "detail": detail}


# --------------------------------------------------------------------------
# Policy configuration
# --------------------------------------------------------------------------


@dataclass
class PolicyConfig:
    """Operator guardrails. Deliberately boring and entirely deterministic."""

    max_txn_amount: Money = field(default_factory=lambda: Money.rupees("25000"))
    max_daily_total: Money = field(default_factory=lambda: Money.rupees("50000"))
    max_txns_per_hour: int = 10
    min_confidence: float = 0.6
    duplicate_window_seconds: int = 120
    require_mandate: bool = True
    #: when True, a payment must match a signed order. Off by default so the system
    #: behaves like UPI does today -- turn it on to see what the order gate changes.
    require_order: bool = False
    order_ttl_seconds: int = 1800

    def to_dict(self) -> dict:
        return {
            "max_txn_amount": self.max_txn_amount.to_rupees_str(),
            "max_daily_total": self.max_daily_total.to_rupees_str(),
            "max_txns_per_hour": self.max_txns_per_hour,
            "min_confidence": self.min_confidence,
            "duplicate_window_seconds": self.duplicate_window_seconds,
            "require_mandate": self.require_mandate,
            "require_order": self.require_order,
            "order_ttl_seconds": self.order_ttl_seconds,
        }


# --------------------------------------------------------------------------
# Mandate validation
# --------------------------------------------------------------------------


def validate_mandate(
    mandate: Mandate | None,
    payee_vpa: str,
    amount: Money,
    order: Order | None = None,
    payer_vpa: str | None = None,
) -> Verdict:
    """Is this payment inside what the user authorised?

    `order` is optional because the category check needs to know what is being
    bought, and only the order says that. Without an order there is no category to
    check, which is precisely the state UPI is in today.

    `payer_vpa` is optional only so direct callers keep working. The policy engine
    always supplies it, because a mandate that does not check whose account it is
    draining is not an authorisation.
    """
    checks: list[dict] = []
    reasons: list[str] = []

    if mandate is None:
        return Verdict(False, "SIM-MANDATE", ["no mandate supplied"],
                       [_check("mandate_present", False, "no mandate")])
    checks.append(_check("mandate_present", True, mandate.umn))

    active = mandate.status is MandateStatus.ACTIVE
    checks.append(_check("mandate_active", active, f"status={mandate.status.value}"))
    if not active:
        reasons.append(f"mandate is {mandate.status.value.lower()}, not active")

    now = utcnow()
    in_window = mandate.valid_from <= now <= mandate.valid_until
    checks.append(_check(
        "mandate_in_date", in_window,
        f"valid {mandate.valid_from.date()} to {mandate.valid_until.date()}",
    ))
    if not in_window:
        reasons.append("mandate is outside its validity window")

    # Whose money is this. An owner can hold several fundable accounts, a bank
    # account and a card among them, and a mandate over one must not license the
    # others. Without this a grant on the cheapest account authorises the lot.
    if payer_vpa is not None:
        payer = validate_vpa(payer_vpa)
        owns_it = payer == mandate.payer_vpa
        checks.append(_check(
            "mandate_covers_this_account", owns_it,
            f"debiting {payer} against a mandate for {mandate.payer_vpa}",
        ))
        if not owns_it:
            reasons.append(
                f"this mandate authorises {mandate.payer_vpa} and the payment is "
                f"drawing on {payer}"
            )

    payee = validate_vpa(payee_vpa)
    payee_ok = "*" in mandate.allowed_payees or payee in mandate.allowed_payees
    checks.append(_check(
        "payee_in_scope", payee_ok,
        f"{payee} against {mandate.allowed_payees}",
    ))
    if not payee_ok:
        reasons.append(f"{payee} is not a permitted payee under this mandate")

    under_per_txn = amount <= mandate.max_amount_per_txn
    checks.append(_check(
        "under_per_txn_cap", under_per_txn,
        f"{amount} against ceiling {mandate.max_amount_per_txn}",
    ))
    if not under_per_txn:
        reasons.append(
            f"{amount} exceeds the per-transaction ceiling of {mandate.max_amount_per_txn}"
        )

    has_headroom = amount <= mandate.remaining
    checks.append(_check(
        "within_total_cap", has_headroom,
        f"{amount} against remaining {mandate.remaining} of {mandate.total_cap}",
    ))
    if not has_headroom:
        reasons.append(
            f"{amount} exceeds the mandate's remaining headroom of {mandate.remaining}"
        )

    # -- the rolling period, separate from the lifetime cap ----------------
    # "Rs 2,000 a month" and "Rs 5,000 in total" are different instructions, and a
    # system that only enforces the second lets a month's budget go in a day.
    period_left = mandate.period_remaining()
    if period_left is not None:
        within_period = amount <= period_left
        checks.append(_check(
            "within_period_budget", within_period,
            f"{amount} against {period_left} left in this "
            f"{mandate.period_days}-day window",
        ))
        if not within_period:
            reasons.append(
                f"{amount} exceeds the {period_left} remaining in this "
                f"{mandate.period_days}-day budget"
            )

    # -- what may be bought, not just from whom ---------------------------
    # The Order has carried a category since it was written. Nothing read it until
    # now, so an authority for dairy would happily pay a fuel invoice.
    if mandate.categories:
        if order is None:
            checks.append(_check(
                "category_in_scope", False,
                f"authority is limited to {mandate.categories} but no order says "
                f"what this is",
            ))
            reasons.append(
                f"this authority is limited to {', '.join(mandate.categories)}, and "
                f"nothing records what is being bought"
            )
        else:
            in_scope = order.category in mandate.categories
            checks.append(_check(
                "category_in_scope", in_scope,
                f"{order.category!r} against {mandate.categories}",
            ))
            if not in_scope:
                reasons.append(
                    f"the order is {order.category!r}, which is outside this "
                    f"authority's {', '.join(mandate.categories)}"
                )

    allowed = not reasons
    return Verdict(allowed, "00" if allowed else "SIM-MANDATE", reasons, checks)


# --------------------------------------------------------------------------
# Policy gate
# --------------------------------------------------------------------------


class PolicyEngine:
    def __init__(
        self,
        store: Store,
        config: PolicyConfig | None = None,
        resolver: Resolver | None = None,
        agent_name: str = "",
        order_signer: OrderSigner = OrderSigner.AGENT,
    ):
        self.store = store
        self.config = config or PolicyConfig()
        # Public keys only. This is what a switch actually holds: it has onboarded
        # these parties and knows their public halves, and it could not forge a
        # signature from any of them if it wanted to.
        self.resolver = resolver or Resolver()
        self.agent_name = agent_name
        self.order_signer = order_signer

    def evaluate(
        self,
        intent: PaymentIntent,
        payer_vpa: str,
        mandate: Mandate | None,
        order: Order | None = None,
        quantity: str | None = None,
    ) -> Verdict:
        """Full gate: intent sanity, mandate, then operator policy.

        `quantity` is the meter reading for a metered order. It arrives at
        settlement, because that is the first moment anybody knows it.
        """
        checks: list[dict] = []
        reasons: list[str] = []

        # -- the agent's own output --------------------------------------
        if not intent.should_pay:
            return Verdict(
                False, "SIM-AGENT", [f"agent declined: {intent.reason}"],
                [_check("agent_proposed_payment", False, intent.reason)],
            )
        checks.append(_check("agent_proposed_payment", True, intent.reason))

        if intent.payee_vpa is None or intent.amount is None:
            return Verdict(
                False, "SIM-AGENT", ["agent proposed a payment without a payee or amount"],
                checks + [_check("intent_complete", False, "missing payee or amount")],
            )
        checks.append(_check("intent_complete", True, f"{intent.amount} to {intent.payee_vpa}"))

        if not intent.amount.is_positive:
            return Verdict(
                False, "SIM-POLICY", [f"non-positive amount {intent.amount}"],
                checks + [_check("amount_positive", False, str(intent.amount))],
            )
        checks.append(_check("amount_positive", True, str(intent.amount)))

        confident = intent.confidence >= self.config.min_confidence
        checks.append(_check(
            "confidence_floor", confident,
            f"{intent.confidence:.2f} against floor {self.config.min_confidence:.2f}",
        ))
        if not confident:
            reasons.append(
                f"agent confidence {intent.confidence:.2f} is below the "
                f"{self.config.min_confidence:.2f} floor"
            )

        # -- payee must exist on the rails --------------------------------
        payee_account = self.store.get_account_by_vpa(intent.payee_vpa)
        checks.append(_check(
            "payee_resolvable", payee_account is not None,
            intent.payee_vpa,
        ))
        if payee_account is None:
            reasons.append(f"{intent.payee_vpa} is not a registered VPA")

        # -- order: does this payment match what the user agreed to? -------
        # This runs before the mandate on purpose. "Can they afford it" is a
        # different question from "did they agree to it", and only the second one
        # notices a Rs 600 charge against a Rs 118 basket.
        if self.config.require_order:
            known = self.resolver.is_registered(intent.payee_vpa)
            checks.append(_check("merchant_key_known", known, intent.payee_vpa))
            if not known:
                reasons.append(f"no registered key for merchant {intent.payee_vpa}")
            else:
                _ok, o_reasons, o_checks = validate_order(
                    order, intent.payee_vpa, intent.amount,
                    self.order_signer, self.resolver,
                    self.agent_name, intent.payee_vpa,
                    timedelta(seconds=self.config.order_ttl_seconds),
                    quantity,
                )
                checks.extend(o_checks)
                reasons.extend(o_reasons)

        # -- mandate -------------------------------------------------------
        if self.config.require_mandate:
            mv = validate_mandate(mandate, intent.payee_vpa, intent.amount, order,
                                  payer_vpa=payer_vpa)
            checks.extend(mv.checks)
            reasons.extend(mv.reasons)

        # -- operator guardrails -------------------------------------------
        under_global = intent.amount <= self.config.max_txn_amount
        checks.append(_check(
            "under_policy_txn_ceiling", under_global,
            f"{intent.amount} against {self.config.max_txn_amount}",
        ))
        if not under_global:
            reasons.append(
                f"{intent.amount} exceeds the policy per-transaction ceiling "
                f"of {self.config.max_txn_amount}"
            )

        recent = self._recent_txns(payer_vpa, hours=24)
        day_total = Money(sum(t.amount.paise for t in recent))
        under_daily = (day_total + intent.amount) <= self.config.max_daily_total
        checks.append(_check(
            "under_daily_total", under_daily,
            f"{day_total} spent today + {intent.amount} against {self.config.max_daily_total}",
        ))
        if not under_daily:
            reasons.append(
                f"would take today's spend to {day_total + intent.amount}, over the "
                f"{self.config.max_daily_total} daily cap"
            )

        last_hour = self._recent_txns(payer_vpa, hours=1)
        under_velocity = len(last_hour) < self.config.max_txns_per_hour
        checks.append(_check(
            "under_velocity_limit", under_velocity,
            f"{len(last_hour)} in the last hour against {self.config.max_txns_per_hour}",
        ))
        if not under_velocity:
            reasons.append(
                f"{len(last_hour)} payments in the last hour hits the velocity limit "
                f"of {self.config.max_txns_per_hour}"
            )

        dup = self._find_duplicate(payer_vpa, intent.payee_vpa, intent.amount)
        checks.append(_check(
            "no_recent_duplicate", dup is None,
            f"prior {dup.txn_id}" if dup else "none in window",
        ))
        if dup is not None:
            reasons.append(
                f"identical payment {dup.txn_id} was raised "
                f"{self.config.duplicate_window_seconds}s ago; suppressing as a duplicate"
            )

        allowed = not reasons
        return Verdict(allowed, "00" if allowed else "SIM-POLICY", reasons, checks)

    # -- helpers -----------------------------------------------------------

    def _recent_txns(self, payer_vpa: str, hours: int):
        cutoff = utcnow() - timedelta(hours=hours)
        counted = {
            TxnState.SETTLED, TxnState.DEBITED, TxnState.CREDITED,
            TxnState.CREDIT_PENDING, TxnState.DEBIT_PENDING, TxnState.TIMED_OUT,
        }
        return [
            t for t in self.store.list_txns(limit=1000)
            if t.payer_vpa == payer_vpa and t.created_at >= cutoff and t.state in counted
        ]

    def _find_duplicate(self, payer_vpa: str, payee_vpa: str, amount: Money):
        cutoff = utcnow() - timedelta(seconds=self.config.duplicate_window_seconds)
        for t in self.store.list_txns(limit=200):
            if (
                t.payer_vpa == payer_vpa
                and t.payee_vpa == validate_vpa(payee_vpa)
                and t.amount == amount
                and t.created_at >= cutoff
                and t.state not in {TxnState.DECLINED, TxnState.REVERSED, TxnState.FAILED}
            ):
                return t
        return None
