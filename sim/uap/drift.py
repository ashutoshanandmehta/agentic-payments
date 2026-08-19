"""
Drift evaluation -- the delta between what was authorised and what was selected.

The industry frames agent payment safety as a spend cap: *did it stay under the
limit*. That is one row in the table below. Drift is the harder question: *did it
buy the thing you meant*.

Every check here is deterministic and total. No model is consulted. The evaluator
is the thing a bank would have to run before authorising, so it must be arithmetic
all the way down.

The evaluator is also **fail-closed**: an unverifiable signature, an unparseable
payload, or a mismatched reference all deny. A drift evaluator that authorises when
confused is worse than none, because it launders the failure as an approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .intent import (
    Intent,
    display_unit,
    Money,
    Quantity,
    Severity,
    Substitution,
    Unit,
    Violation,
    unit_price,
)
from .mandate import Keypair, SignedMandate


@dataclass
class DriftReport:
    violations: list[Violation] = field(default_factory=list)
    checks_run: int = 0
    #: 0.0 == cart matches intent exactly; grows with the magnitude of deviation
    score: float = 0.0

    @property
    def fatal(self) -> list[Violation]:
        return [v for v in self.violations if v.severity is Severity.FATAL]

    @property
    def authorised(self) -> bool:
        return not self.fatal

    def add(self, v: Violation, magnitude: float = 1.0) -> None:
        self.violations.append(v)
        if v.severity is Severity.FATAL:
            self.score += magnitude

    def render(self) -> str:
        if not self.violations:
            return f"  no drift ({self.checks_run} checks passed)"
        return "\n".join(f"  {v}" for v in self.violations)


def _ratio_over(actual: int, ceiling: int) -> float:
    """How far past a ceiling, as a fraction of the ceiling. Used for scoring."""
    if ceiling <= 0:
        return 1.0
    return max(0.0, (actual - ceiling) / ceiling)


def evaluate(
    intent: Intent,
    intent_mandate: SignedMandate,
    cart_mandate: SignedMandate,
    principal_key: Keypair,
    agent_key: Keypair,
    item_categories: dict[str, str] | None = None,
) -> DriftReport:
    """
    Compare a signed cart against a signed intent.

    `item_categories` maps canonical item key -> category, used only to adjudicate
    SAME_CATEGORY substitution.
    """
    r = DriftReport()
    cats = item_categories or {}

    # -- 0. the chain must verify before anything else is worth checking -----

    r.checks_run += 1
    if not intent_mandate.verify_with(principal_key):
        r.add(Violation(
            "signature", "intent mandate signature does not verify",
            "valid signature by principal", "invalid",
        ), magnitude=10.0)
        return r  # nothing downstream is trustworthy

    r.checks_run += 1
    if not cart_mandate.verify_with(agent_key):
        r.add(Violation(
            "signature", "cart mandate signature does not verify",
            "valid signature by agent", "invalid",
        ), magnitude=10.0)
        return r

    r.checks_run += 1
    if cart_mandate.payload.get("intent_ref") != intent_mandate.id:
        r.add(Violation(
            "binding", "cart does not reference this intent",
            intent_mandate.id, str(cart_mandate.payload.get("intent_ref")),
        ), magnitude=10.0)
        return r

    lines = cart_mandate.payload.get("lines", [])
    r.checks_run += 1
    if not lines:
        r.add(Violation("empty", "cart contains no lines", ">=1 line", "0"))
        return r

    # -- 1. merchant allow-list ---------------------------------------------

    for ln in lines:
        r.checks_run += 1
        if intent.allowed_merchants and ln["merchant"] not in intent.allowed_merchants:
            r.add(Violation(
                "merchant", f"'{ln['merchant']}' is not an authorised seller",
                "{" + ", ".join(sorted(intent.allowed_merchants)) + "}", ln["merchant"],
            ))

    # -- 2. item identity / substitution ------------------------------------

    for ln in lines:
        r.checks_run += 1
        got = ln["sku"].split(":")[0]
        if got == intent.item:
            continue
        if intent.substitution is Substitution.NONE:
            r.add(Violation(
                "substitution", "item substituted but no substitution was authorised",
                intent.item, got,
            ))
        elif intent.substitution is Substitution.SAME_CATEGORY:
            if cats.get(got) != cats.get(intent.item):
                r.add(Violation(
                    "substitution", "substituted item is in a different category",
                    f"category of {intent.item}", f"{got} ({cats.get(got, 'unknown')})",
                ))
        elif intent.substitution is Substitution.SAME_ITEM:
            r.add(Violation(
                "substitution", "different item key under SAME_ITEM policy",
                intent.item, got,
            ))

    # -- 3. quantity, normalised to base units ------------------------------

    total_base = 0
    for ln in lines:
        q = Quantity(Decimal(ln["quantity"]["amount"]), Unit(ln["quantity"]["unit"]))
        r.checks_run += 1
        if not q.commensurable_with(intent.max_quantity):
            r.add(Violation(
                "unit", "quantity is not commensurable with the authorised unit",
                intent.max_quantity.base_unit.value, q.base_unit.value,
            ))
            continue
        total_base += q.base_amount

    ceiling_base = intent.max_quantity.base_amount
    r.checks_run += 1
    if total_base > ceiling_base:
        r.add(Violation(
            "quantity", "cart quantity exceeds the authorised quantity",
            f"{ceiling_base}{intent.max_quantity.base_unit.value}",
            f"{total_base}{intent.max_quantity.base_unit.value}",
        ), magnitude=_ratio_over(total_base, ceiling_base))

    # -- 4. unit price, normalised. this is the unit-confusion check ---------

    if intent.max_unit_price is not None:
        for ln in lines:
            q = Quantity(Decimal(ln["quantity"]["amount"]), Unit(ln["quantity"]["unit"]))
            if q.base_amount <= 0:
                continue
            r.checks_run += 1
            actual = unit_price(Money(ln["line_total_paise"]), q)
            if actual > intent.max_unit_price:
                per = display_unit(q.base_unit)
                r.add(Violation(
                    "unit_price",
                    f"effective unit price on '{ln['title']}' exceeds the ceiling",
                    f"{Money(intent.max_unit_price)}/{per}",
                    f"{Money(actual)}/{per}",
                ), magnitude=_ratio_over(actual, intent.max_unit_price))

    # -- 5. line arithmetic must be self-consistent -------------------------

    for ln in lines:
        q = Quantity(Decimal(ln["quantity"]["amount"]), Unit(ln["quantity"]["unit"]))
        if q.base_amount <= 0:
            continue
        r.checks_run += 1
        # recompute the unit price implied by the line total and compare against the
        # one the merchant declared. an inflated line total shows up here even when
        # the declared unit price is left looking innocent.
        implied = unit_price(Money(ln["line_total_paise"]), q)
        if implied != ln["unit_price_paise"]:
            per = display_unit(q.base_unit)
            r.add(Violation(
                "arithmetic",
                f"line total on '{ln['title']}' is inconsistent with its declared unit price",
                f"{Money(ln['unit_price_paise'])}/{per}", f"{Money(implied)}/{per}",
            ))

    # -- 6. totals ----------------------------------------------------------

    charged = Money(cart_mandate.payload["charged_total_paise"])
    quoted = Money(cart_mandate.payload["quoted_total_paise"])
    summed = Money(sum(ln["line_total_paise"] for ln in lines))

    r.checks_run += 1
    if summed.paise != charged.paise:
        r.add(Violation(
            "arithmetic", "charged total does not equal the sum of lines",
            str(summed), str(charged),
        ))

    r.checks_run += 1
    if charged.paise > intent.max_total.paise:
        r.add(Violation(
            "total", "charged total exceeds the authorised maximum",
            str(intent.max_total), str(charged),
        ), magnitude=_ratio_over(charged.paise, intent.max_total.paise))

    # -- 7. quote drift: what was shown at discovery vs what is being charged

    r.checks_run += 1
    if quoted.paise > 0 and charged.paise > quoted.paise:
        drift_bps = int((charged.paise - quoted.paise) * 10_000 / quoted.paise)
        if drift_bps > intent.max_price_drift_bps:
            r.add(Violation(
                "quote_drift",
                "price charged exceeds the price quoted at discovery",
                f"<= {intent.max_price_drift_bps}bps above {quoted}",
                f"{drift_bps}bps ({charged})",
            ), magnitude=drift_bps / 10_000)

    return r
