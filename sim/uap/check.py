"""
The two checks at the payment boundary.

Check A -- does the payment request still match the cart?
          Nothing changed between the cart being agreed and the money moving.

Check B -- does the cart fit inside the authority?
          The agent stayed within what the human allowed.

Both are arithmetic. No language model is consulted, because a bank cannot refuse a
payment on a probability -- it needs a reason it can put in a dispute file.

The checker is **fail-closed**, meaning: if anything is unverifiable, unreadable or
inconsistent, the answer is refuse. A checker that approves when confused is worse
than no checker, because it turns a failure into an approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .authority import Money, PaymentAuthority, Severity, Violation
from .mandate import CartSigner, Keypair, SignedRecord


@dataclass
class CheckResult:
    violations: list[Violation] = field(default_factory=list)
    checks_run: int = 0
    #: 0.0 means the payment matched exactly. higher means further outside the rules.
    score: float = 0.0

    @property
    def fatal(self) -> list[Violation]:
        return [v for v in self.violations if v.severity is Severity.FATAL]

    @property
    def passed(self) -> bool:
        return not self.fatal

    def add(self, v: Violation, magnitude: float = 1.0) -> None:
        self.violations.append(v)
        if v.severity is Severity.FATAL:
            self.score += magnitude


def _over(actual: int, ceiling: int) -> float:
    """How far past a limit, as a fraction of the limit."""
    if ceiling <= 0:
        return 1.0
    return max(0.0, (actual - ceiling) / ceiling)


def check(
    authority: PaymentAuthority,
    authority_rec: SignedRecord,
    cart_rec: SignedRecord,
    request_rec: SignedRecord,
    principal_key: Keypair,
    agent_key: Keypair,
    merchant_key: Keypair,
    cart_signer: CartSigner,
    now: int,
    spent_so_far: Money,
    payments_so_far: int,
    seen_nonces: set[str] | None = None,
) -> CheckResult:
    r = CheckResult()
    seen = seen_nonces or set()

    # -- 0. signatures. nothing below is worth reading if these fail ---------

    r.checks_run += 1
    if not authority_rec.verify_by(principal_key):
        r.add(Violation("signature", "the authority was not signed by the human",
                        "valid signature", "invalid"), 10.0)
        return r

    r.checks_run += 1
    if not request_rec.verify_by(agent_key):
        r.add(Violation("signature", "the payment request was not signed by the agent",
                        "valid signature", "invalid"), 10.0)
        return r

    # who must have signed the cart depends on the design being tested
    required = {
        CartSigner.AGENT: [(agent_key, "agent")],
        CartSigner.MERCHANT: [(merchant_key, "shop")],
        CartSigner.BOTH: [(agent_key, "agent"), (merchant_key, "shop")],
    }[cart_signer]
    for key, who in required:
        r.checks_run += 1
        if not cart_rec.verify_by(key):
            r.add(Violation("signature", f"the cart was not signed by the {who}",
                            f"signature by {who}", "missing or invalid"), 10.0)
            return r

    r.checks_run += 1
    if request_rec.payload.get("authority_ref") != authority_rec.id:
        r.add(Violation("binding", "the request points at a different authority",
                        authority_rec.id, str(request_rec.payload.get("authority_ref"))), 10.0)
        return r

    # ======================================================================
    # CHECK A -- does the payment request still match the cart?
    # ======================================================================

    cart = cart_rec.payload
    req = request_rec.payload

    r.checks_run += 1
    if req.get("cart_ref") != cart.get("cart_id"):
        r.add(Violation("binding", "the request points at a different cart",
                        str(cart.get("cart_id")), str(req.get("cart_ref"))), 10.0)
        return r

    r.checks_run += 1
    if req["amount_paise"] != cart["total_paise"]:
        r.add(Violation(
            "amount_changed",
            "the amount being paid is not the amount on the cart",
            str(Money(cart["total_paise"])), str(Money(req["amount_paise"])),
        ), _over(req["amount_paise"], cart["total_paise"]))

    r.checks_run += 1
    if req["merchant"] != cart["merchant"]:
        r.add(Violation(
            "payee_changed", "the money is going to a different shop than the cart",
            cart["merchant"], req["merchant"],
        ), 5.0)

    r.checks_run += 1
    line_sum = sum(l["amount_paise"] for l in cart["lines"])
    if line_sum != cart["total_paise"]:
        r.add(Violation(
            "cart_arithmetic", "the cart total is not the sum of its lines",
            str(Money(line_sum)), str(Money(cart["total_paise"])),
        ))

    r.checks_run += 1
    if req["requested_at"] < cart["agreed_at"]:
        r.add(Violation(
            "ordering", "the payment was requested before the cart was agreed",
            f">= tick {cart['agreed_at']}", f"tick {req['requested_at']}",
        ))

    # ======================================================================
    # CHECK B -- does the cart fit inside the authority?
    # ======================================================================

    total = Money(cart["total_paise"])

    r.checks_run += 1
    if authority.allowed_merchants and cart["merchant"] not in authority.allowed_merchants:
        r.add(Violation(
            "merchant", "this shop is not one the human approved",
            "{" + ", ".join(sorted(authority.allowed_merchants)) + "}", cart["merchant"],
        ))

    r.checks_run += 1
    if (authority.allowed_categories is not None
            and cart["category"] not in authority.allowed_categories):
        r.add(Violation(
            "category", "this category is not one the human approved",
            "{" + ", ".join(sorted(authority.allowed_categories)) + "}", cart["category"],
        ))

    r.checks_run += 1
    if total.paise > authority.max_per_payment.paise:
        r.add(Violation(
            "per_payment", "this single payment is over the per-payment limit",
            str(authority.max_per_payment), str(total),
        ), _over(total.paise, authority.max_per_payment.paise))

    r.checks_run += 1
    running = spent_so_far + total
    if running.paise > authority.max_total.paise:
        r.add(Violation(
            "budget", "this payment takes the total over the authorised budget",
            str(authority.max_total), f"{running} ({spent_so_far} already spent)",
        ), _over(running.paise, authority.max_total.paise))

    r.checks_run += 1
    if payments_so_far + 1 > authority.max_payments:
        r.add(Violation(
            "count", "this authority has already been used the maximum number of times",
            f"{authority.max_payments} payment(s)", f"attempt {payments_so_far + 1}",
        ))

    r.checks_run += 1
    if not (authority.valid_from <= req["requested_at"] <= authority.valid_until):
        r.add(Violation(
            "window", "the payment is outside the authority's validity window",
            f"ticks {authority.valid_from}-{authority.valid_until}",
            f"tick {req['requested_at']}",
        ))

    # a retry of an already-settled payment is a double debit, not a new payment
    r.checks_run += 1
    if req["nonce"] in seen:
        r.add(Violation(
            "replay", "this exact payment has already been settled once",
            "an unused reference", f"nonce {req['nonce']} seen before",
        ), 3.0)

    return r
