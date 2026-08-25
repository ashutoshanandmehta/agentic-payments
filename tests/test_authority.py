"""
Tests for the authority, the rail it binds to, and who could enforce it.

This is the thesis, as assertions.

`test_consent.py` shows the order gate refuses an overcharge. These tests ask the
question that comes before it: **could anyone on UPI actually run that gate?** The
answer today is no, and the tests say why -- every party is either blind or
conflicted.

They also pin down the authority fields the brief names and `Mandate` never had:
a category scope and a rolling period budget.

Run with:  python3 tests/test_authority.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from authority import (  # noqa: E402
    RAIL_LIMITS,
    Rail,
    check_expressible,
    compare_rails,
)
from consent import Order  # noqa: E402
from core import Money  # noqa: E402
from enforcement import (  # noqa: E402
    UPI_TODAY,
    Check,
    Evidence,
    Party,
    report,
    who_can_enforce,
    with_cart_reference,
)
from models import utcnow  # noqa: E402
from orchestrator import RailCannotExpress  # noqa: E402
from policy import validate_mandate  # noqa: E402
import sim as simwiring  # noqa: E402


# --------------------------------------------------------------------------
# Which rail can carry which authority
# --------------------------------------------------------------------------

class TestRailExpressiveness(unittest.TestCase):
    """Section IV of the brief records the authority as a ReservePay block.
    Section II-B says ReservePay names one merchant. Both cannot hold."""

    #: an agent reordering a consumable across shops, groceries only
    THESIS_CASE = (["brewhouse@ybl", "cloudhost@okaxis"], ["groceries"])

    def test_no_rail_carries_the_thesis_case(self):
        """The finding. The user says something no primitive can record."""
        payees, cats = self.THESIS_CASE
        results = compare_rails(payees, cats, Money.rupees("5000"))
        self.assertEqual([r for r in results.values() if r.expressible], [])

    def test_reservepay_cannot_name_two_merchants(self):
        payees, cats = self.THESIS_CASE
        losses = check_expressible(Rail.UPI_RESERVEPAY, payees, cats).losses
        self.assertTrue(any("one named merchant" in l for l in losses))

    def test_circle_cannot_name_any_merchant(self):
        """Device delegation has no payee scope at all."""
        losses = check_expressible(Rail.UPI_CIRCLE, ["brewhouse@ybl"], []).losses
        self.assertTrue(any("device, not a payee" in l for l in losses))

    def test_neither_upi_rail_knows_what_was_bought(self):
        for rail in (Rail.UPI_RESERVEPAY, Rail.UPI_CIRCLE):
            losses = check_expressible(rail, ["brewhouse@ybl"], ["dairy"]).losses
            self.assertTrue(any("what was bought" in l for l in losses), rail)

    def test_the_card_rail_keeps_scope_but_moves_the_money(self):
        """It can say everything. The cost is where the funds sit."""
        payees, cats = self.THESIS_CASE
        result = check_expressible(Rail.CARD_TOKEN, payees, cats)
        self.assertFalse(result.expressible)
        self.assertEqual(len(result.losses), 1)
        self.assertIn("the agent controls", result.losses[0])

    def test_the_control_case_rides_reservepay_fine(self):
        """One known merchant, no category. What UPI was actually built for."""
        result = check_expressible(
            Rail.UPI_RESERVEPAY, ["brewhouse@ybl"], [], Money.rupees("500")
        )
        self.assertTrue(result.expressible, result.losses)

    def test_the_published_ceiling_is_enforced(self):
        result = check_expressible(
            Rail.UPI_RESERVEPAY, ["brewhouse@ybl"], [], Money.rupees("25000")
        )
        self.assertFalse(result.expressible)
        self.assertTrue(any("ceiling" in l for l in result.losses))

    def test_every_rail_limit_is_sourced(self):
        """Each figure has to say where it came from, so it can be checked."""
        for rail, limits in RAIL_LIMITS.items():
            self.assertTrue(limits.source_note, rail)


# --------------------------------------------------------------------------
# Who could run the check
# --------------------------------------------------------------------------

class TestEnforcementPoint(unittest.TestCase):
    """AP2 puts the binding check at the Merchant Payment Processor.
    UPI has no such party. So who runs it?"""

    def test_neither_check_is_enforceable_on_upi_today(self):
        """The central claim, as one assertion."""
        self.assertEqual(sorted(report(UPI_TODAY)["unenforceable"]), ["A", "B"])
        for check in Check:
            self.assertEqual(who_can_enforce(check, UPI_TODAY), [], check)

    def test_the_merchant_can_see_the_cart_but_profits_from_inflating_it(self):
        merchant = UPI_TODAY[Party.MERCHANT]
        self.assertTrue(merchant.can_see_enough_for(Check.A))
        self.assertFalse(merchant.trusted)
        self.assertFalse(merchant.can_enforce(Check.A))

    def test_the_remitter_bank_is_trusted_but_blind(self):
        """It holds the authority and does the debit. It has never seen a cart."""
        bank = UPI_TODAY[Party.REMITTER_BANK]
        self.assertTrue(bank.trusted)
        self.assertIn(Evidence.AUTHORITY, bank.sees)
        self.assertNotIn(Evidence.CART, bank.sees)
        self.assertEqual(bank.missing_for(Check.B), ["cart"])

    def test_the_agent_holds_everything_and_is_the_point_of_the_check(self):
        agent = UPI_TODAY[Party.AGENT]
        self.assertTrue(agent.can_see_enough_for(Check.A))
        self.assertTrue(agent.can_see_enough_for(Check.B))
        self.assertFalse(agent.can_enforce(Check.A))

    def test_ap2s_answer_does_not_exist_on_this_rail(self):
        self.assertFalse(UPI_TODAY[Party.MERCHANT_PROCESSOR].exists_on_upi)

    def test_blindness_and_conflict_are_reported_differently(self):
        """Only one of the two is fixable by changing the rail."""
        reasons = {
            f["party"]: f["reason"]
            for f in report(UPI_TODAY)["findings"] if f["check"] == "B"
        }
        self.assertTrue(reasons["remitter_bank"].startswith("blind"))
        self.assertTrue(reasons["agent"].startswith("conflicted"))

    def test_one_field_makes_both_checks_enforceable(self):
        """The proposal, stated as a diff rather than an argument."""
        proposed = report(with_cart_reference())
        self.assertEqual(proposed["unenforceable"], [])
        self.assertEqual(proposed["enforcers"]["A"], ["remitter_bank"])
        self.assertEqual(proposed["enforcers"]["B"], ["remitter_bank"])

    def test_the_field_does_not_launder_a_conflicted_party(self):
        """Giving the merchant the authority would not make it trustworthy."""
        topology = with_cart_reference(to=Party.MERCHANT)
        self.assertFalse(topology[Party.MERCHANT].can_enforce(Check.A))


# --------------------------------------------------------------------------
# The authority fields the brief names
# --------------------------------------------------------------------------

class AuthorityCase(unittest.TestCase):

    def setUp(self):
        self.db = tempfile.mktemp(suffix=".db")
        self.sim = simwiring.build(db_path=self.db, fresh=True)
        simwiring.seed(self.sim)
        self.now = utcnow()

    def tearDown(self):
        self.sim.close()
        if os.path.exists(self.db):
            os.remove(self.db)

    def authority(self, **kw):
        params = dict(
            payer_vpa=simwiring.USER_VPA,
            allowed_payees=[simwiring.MERCHANT_VPA],
            max_amount_per_txn=Money.rupees("500"),
            total_cap=Money.rupees("5000"),
            valid_from=self.now - timedelta(days=1),
            valid_until=self.now + timedelta(days=90),
            purpose="test",
        )
        params.update(kw)
        return self.sim.orchestrator.create_mandate(**params)


class TestRailBinding(AuthorityCase):

    def test_creation_refuses_what_the_rail_cannot_say(self):
        """Better to refuse than to record a narrower authority than the user set."""
        with self.assertRaises(RailCannotExpress) as caught:
            self.authority(
                allowed_payees=[simwiring.MERCHANT_VPA,
                                simwiring.SECOND_MERCHANT_VPA],
                rail=Rail.UPI_RESERVEPAY.value,
            )
        self.assertTrue(caught.exception.losses)

    def test_an_expressible_authority_is_created(self):
        m = self.authority(rail=Rail.UPI_RESERVEPAY.value)
        self.assertEqual(m.rail, Rail.UPI_RESERVEPAY.value)

    def test_no_rail_named_means_no_constraint_check(self):
        """The default stays the way the simulator behaved before."""
        m = self.authority(allowed_payees=["*"], categories=["dairy"])
        self.assertIsNone(m.rail)


class TestCategoryScope(AuthorityCase):
    """Order has carried a category since it was written. Nothing read it."""

    def setUp(self):
        super().setUp()
        self.mandate = self.authority(categories=["dairy"])

    def order(self, category):
        return Order.build("O1", simwiring.MERCHANT_VPA,
                           [("Item", "118")], category=category)

    def verdict(self, category):
        return validate_mandate(
            self.mandate, simwiring.MERCHANT_VPA, Money.rupees("118"),
            self.order(category),
        )

    def test_an_in_scope_order_passes(self):
        self.assertTrue(self.verdict("dairy").allowed)

    def test_an_out_of_scope_order_is_refused(self):
        v = self.verdict("fuel")
        self.assertFalse(v.allowed)
        self.assertIn("outside this authority", " ".join(v.reasons))

    def test_a_scoped_authority_refuses_a_payment_with_no_order(self):
        """If nothing says what this is, a category limit cannot be honoured."""
        v = validate_mandate(
            self.mandate, simwiring.MERCHANT_VPA, Money.rupees("118"), None
        )
        self.assertFalse(v.allowed)

    def test_an_unscoped_authority_still_takes_anything(self):
        """The household finding: the loosest grant sets the real policy."""
        loose = self.authority(categories=[])
        v = validate_mandate(
            loose, simwiring.MERCHANT_VPA, Money.rupees("118"), self.order("fuel")
        )
        self.assertTrue(v.allowed, v.reasons)


class TestPeriodBudget(AuthorityCase):
    """'Rs 200 a month' is a different instruction from 'Rs 5,000 in total'."""

    def setUp(self):
        super().setUp()
        self.mandate = self.authority(
            period_cap=Money.rupees("200"), period_days=30
        )

    def check(self, amount):
        return validate_mandate(
            self.mandate, simwiring.MERCHANT_VPA, Money.rupees(amount)
        )

    def test_the_window_starts_when_the_authority_does(self):
        self.assertIsNotNone(self.mandate.period_started_at)
        self.assertEqual(self.mandate.period_remaining(), Money.rupees("200"))

    def test_the_period_bites_before_the_lifetime_cap(self):
        """Rs 450 is under the Rs 500 txn ceiling and the Rs 5,000 total."""
        v = self.check("450")
        self.assertFalse(v.allowed)
        self.assertIn("30-day budget", " ".join(v.reasons))

    def test_spending_consumes_the_window(self):
        self.sim.store.consume_mandate(self.mandate.umn, Money.rupees("150"))
        reloaded = self.sim.store.get_mandate(self.mandate.umn)
        self.assertEqual(reloaded.period_consumed, Money.rupees("150"))
        self.assertEqual(reloaded.period_remaining(), Money.rupees("50"))

    def test_the_window_rolls_over_when_it_closes(self):
        self.sim.store.consume_mandate(self.mandate.umn, Money.rupees("200"))
        reloaded = self.sim.store.get_mandate(self.mandate.umn)
        self.assertEqual(reloaded.period_remaining(), Money.zero())

        # wind the window back past its end
        reloaded.period_started_at = self.now - timedelta(days=31)
        self.sim.store.save_mandate(reloaded)

        rolled = self.sim.store.get_mandate(self.mandate.umn)
        self.assertTrue(rolled.period_elapsed())
        self.assertEqual(rolled.period_remaining(), Money.rupees("200"))

    def test_a_reversal_gives_the_window_back(self):
        self.sim.store.consume_mandate(self.mandate.umn, Money.rupees("150"))
        self.sim.store.release_mandate(self.mandate.umn, Money.rupees("150"))
        reloaded = self.sim.store.get_mandate(self.mandate.umn)
        self.assertEqual(reloaded.period_consumed, Money.zero())

    def test_no_period_means_no_period_check(self):
        plain = self.authority()
        self.assertIsNone(plain.period_remaining())
        self.assertTrue(
            validate_mandate(
                plain, simwiring.MERCHANT_VPA, Money.rupees("450")
            ).allowed
        )

    def test_it_survives_sqlite(self):
        reloaded = self.sim.store.get_mandate(self.mandate.umn)
        self.assertEqual(reloaded.period_cap, Money.rupees("200"))
        self.assertEqual(reloaded.period_days, 30)
        self.assertEqual(reloaded.categories, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
