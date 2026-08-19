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
from consent import Keypair, Order, OrderSigner, validate_order
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
    mandate: Mandate | None, payee_vpa: str, amount: Money
) -> Verdict:
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
        agent_key: Keypair | None = None,
        merchant_keys: dict[str, Keypair] | None = None,
        order_signer: OrderSigner = OrderSigner.AGENT,
    ):
        self.store = store
        self.config = config or PolicyConfig()
        # the switch holds registered public keys; here it holds the keypairs
        self.agent_key = agent_key
        self.merchant_keys = merchant_keys or {}
        self.order_signer = order_signer

    def evaluate(
        self,
        intent: PaymentIntent,
        payer_vpa: str,
        mandate: Mandate | None,
        order: Order | None = None,
    ) -> Verdict:
        """Full gate: intent sanity, mandate, then operator policy."""
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
            mkey = self.merchant_keys.get(intent.payee_vpa)
            if mkey is None:
                reasons.append(f"no registered key for merchant {intent.payee_vpa}")
                checks.append(_check("merchant_key_known", False, intent.payee_vpa))
            else:
                _ok, o_reasons, o_checks = validate_order(
                    order, intent.payee_vpa, intent.amount,
                    self.order_signer, self.agent_key, mkey,
                    timedelta(seconds=self.config.order_ttl_seconds),
                )
                checks.extend(o_checks)
                reasons.extend(o_reasons)

        # -- mandate -------------------------------------------------------
        if self.config.require_mandate:
            mv = validate_mandate(mandate, intent.payee_vpa, intent.amount)
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
