"""
Tests for metered purchases.

The beachhead use cases in the brief are all metered. A charging session, a battery
swap, a tanker of water. None of them has a basket, and none of them has a total
anybody knows in advance. The amount falls out of a measured quantity once the thing
is over.

An order gate built on an agreed total cannot serve any of them. It refuses the
honest undercharge as hard as the overcharge, because it only knows how to check
equality.

So the user agrees a rate and a ceiling instead, and settlement is checked against a
meter reading. These tests pin down what that does and does not protect.

Run with:  python3 tests/test_metered.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from consent import Order, OrderSigner, Tariff, canonical  # noqa: E402
from core import Money  # noqa: E402
from models import PaymentIntent  # noqa: E402
from policy import PolicyConfig  # noqa: E402
import sim as simwiring  # noqa: E402


# --------------------------------------------------------------------------
# Money at a rate
# --------------------------------------------------------------------------

class TestMoneyTimes(unittest.TestCase):

    def test_whole_quantities(self):
        self.assertEqual(Money.rupees("15").times("12"), Money.rupees("180"))
        self.assertEqual(Money.rupees("15").times(12), Money.rupees("180"))

    def test_fractional_quantities(self):
        self.assertEqual(Money.rupees("15").times("11.2"), Money.rupees("168"))
        self.assertEqual(Money.rupees("2.50").times("4.5"), Money.rupees("11.25"))

    def test_it_rounds_half_up_to_the_paisa(self):
        """13.333 kWh at Rs 15 is Rs 199.995. Somebody has to decide."""
        self.assertEqual(Money.rupees("15").times("13.333"), Money.rupees("200"))
        self.assertEqual(Money.rupees("1").times("0.005"), Money.rupees("0.01"))
        self.assertEqual(Money.rupees("1").times("0.004"), Money.zero())

    def test_zero_quantity_costs_nothing(self):
        self.assertEqual(Money.rupees("15").times("0"), Money.zero())

    def test_floats_are_refused(self):
        """Same reason Money.rupees refuses them. A reading arrives as text."""
        with self.assertRaises(TypeError):
            Money.rupees("15").times(11.2)

    def test_negative_and_nonsense_quantities_are_refused(self):
        with self.assertRaises(ValueError):
            Money.rupees("15").times("-1")
        with self.assertRaises(ValueError):
            Money.rupees("15").times("twelve")


class TestTariff(unittest.TestCase):

    def test_expected_uses_the_rate(self):
        t = Tariff(rate=Money.rupees("15"), unit="kWh", cap=Money.rupees("250"))
        self.assertEqual(t.expected("11.2"), Money.rupees("168"))


# --------------------------------------------------------------------------
# The order carries the tariff, and the signature covers it
# --------------------------------------------------------------------------

class TestMeteredOrder(unittest.TestCase):

    def order(self):
        return Order.metered("CHG-1", "brewhouse@ybl", "Charging session",
                             rate="15", unit="kWh", cap="250", max_quantity="20")

    def test_it_is_marked_metered(self):
        o = self.order()
        self.assertTrue(o.is_metered)
        self.assertFalse(Order.build("O", "brewhouse@ybl", [("x", "10")]).is_metered)

    def test_total_is_set_to_the_ceiling(self):
        """Anything reading total without knowing about tariffs sees the worst case."""
        self.assertEqual(self.order().total, Money.rupees("250"))

    def test_the_tariff_is_inside_the_signed_payload(self):
        """A rate that could be swapped after signing would leave only the cap."""
        o = self.order()
        self.assertIn("tariff", o.payload())
        self.assertEqual(o.payload()["tariff"]["rate_paise"], 1500)

    def test_swapping_the_rate_changes_the_signed_bytes(self):
        o = self.order()
        before = canonical(o.payload())
        padded = o.tamper(tariff=Tariff(rate=Money.rupees("25"), unit="kWh",
                                        cap=Money.rupees("250")))
        self.assertNotEqual(before, canonical(padded.payload()))

    def test_a_plain_order_carries_a_null_tariff(self):
        o = Order.build("O", "brewhouse@ybl", [("x", "10")])
        self.assertIsNone(o.payload()["tariff"])


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------

class MeteredGateCase(unittest.TestCase):
    """An EV charging session. Rs 15 per kWh, Rs 250 ceiling, 20 kWh limit."""

    def setUp(self):
        self.db = tempfile.mktemp(suffix=".db")
        self.sim = simwiring.build(db_path=self.db, fresh=True,
                                   policy_config=PolicyConfig(require_order=True))
        seeded = simwiring.seed(self.sim)
        self.mandate = self.sim.store.get_mandate(seeded["mandate"]["umn"])
        self.order = Order.metered(
            "CHG-1", simwiring.MERCHANT_VPA, "Charging session",
            rate="15", unit="kWh", cap="250", max_quantity="20",
        )
        self.order.sign(OrderSigner.AGENT, self.sim.agent_key,
                        self.sim.merchant_keys[simwiring.MERCHANT_VPA])

    def tearDown(self):
        self.sim.close()
        if os.path.exists(self.db):
            os.remove(self.db)

    def verdict(self, amount, quantity, order=None):
        return self.sim.policy.evaluate(
            PaymentIntent(True, simwiring.MERCHANT_VPA, Money.rupees(str(amount)),
                          "charging session", 0.95, "rule"),
            simwiring.USER_VPA, self.mandate, order or self.order, quantity=quantity,
        )

    def named(self, v, name):
        return next(c for c in v.checks if c["check"] == name)


class TestMeteredSettlement(MeteredGateCase):

    def test_an_honest_session_settles(self):
        v = self.verdict("168", "11.2")
        self.assertTrue(v.allowed, v.reasons)

    def test_an_honest_session_of_any_size_settles(self):
        """The old gate refused every amount but one. This is the whole point."""
        for qty, amount in (("1", "15"), ("7.4", "111"), ("16", "240")):
            self.assertTrue(self.verdict(amount, qty).allowed, f"{qty} {amount}")

    def test_rounding_is_accepted(self):
        """13.333 kWh at Rs 15 is Rs 199.995, which settles at Rs 200.00."""
        self.assertTrue(self.verdict("200", "13.333").allowed)

    def test_a_padded_rate_is_refused(self):
        v = self.verdict("190", "11.2")
        self.assertFalse(v.allowed)
        self.assertFalse(self.named(v, "amount_matches_tariff")["passed"])
        self.assertIn("comes to", " ".join(v.reasons))

    def test_undercharging_is_also_refused(self):
        """Not a kindness. A wrong amount is a wrong amount in either direction."""
        self.assertFalse(self.verdict("150", "11.2").allowed)

    def test_no_reading_means_nothing_can_be_checked(self):
        v = self.verdict("168", None)
        self.assertFalse(v.allowed)
        self.assertFalse(self.named(v, "meter_reading_present")["passed"])

    def test_a_runaway_meter_is_caught(self):
        v = self.verdict("450", "30")
        self.assertFalse(v.allowed)
        self.assertFalse(self.named(v, "within_max_quantity")["passed"])


class TestTheCeilingIsTheRealControl(MeteredGateCase):
    """The rate check assumes the meter is honest. The ceiling does not."""

    def test_a_correct_rate_over_the_ceiling_is_refused(self):
        v = self.verdict("270", "18")
        self.assertFalse(v.allowed)
        self.assertTrue(self.named(v, "amount_matches_tariff")["passed"])
        self.assertFalse(self.named(v, "under_agreed_cap")["passed"])

    def test_the_ceiling_is_checked_even_with_no_reading(self):
        """A missing reading must not become a way around the cap."""
        v = self.verdict("900", None)
        self.assertFalse(self.named(v, "under_agreed_cap")["passed"])

    def test_a_tariff_without_a_quantity_limit_still_has_a_ceiling(self):
        loose = Order.metered("CHG-2", simwiring.MERCHANT_VPA, "Session",
                              rate="15", unit="kWh", cap="250")
        loose.sign(OrderSigner.AGENT, self.sim.agent_key,
                   self.sim.merchant_keys[simwiring.MERCHANT_VPA])
        v = self.verdict("300", "20", order=loose)
        self.assertFalse(v.allowed)
        self.assertFalse(self.named(v, "under_agreed_cap")["passed"])


class TestPlainOrdersAreUnaffected(MeteredGateCase):
    """The itemised path must behave exactly as it did before."""

    def test_an_itemised_order_still_demands_an_exact_total(self):
        plain = Order.build("ORD-1", simwiring.MERCHANT_VPA,
                            [("Monthly plan", "99"), ("GST", "19")])
        plain.sign(OrderSigner.AGENT, self.sim.agent_key,
                   self.sim.merchant_keys[simwiring.MERCHANT_VPA])
        self.assertTrue(self.verdict("118", None, order=plain).allowed)
        self.assertFalse(self.verdict("600", None, order=plain).allowed)

    def test_a_quantity_on_an_itemised_order_is_ignored(self):
        plain = Order.build("ORD-1", simwiring.MERCHANT_VPA, [("Item", "118")])
        plain.sign(OrderSigner.AGENT, self.sim.agent_key,
                   self.sim.merchant_keys[simwiring.MERCHANT_VPA])
        self.assertTrue(self.verdict("118", "99", order=plain).allowed)


class TestMeteredEndToEnd(MeteredGateCase):

    def test_a_session_settles_through_the_rails(self):
        result = self.sim.orchestrator.execute(
            intent=PaymentIntent(True, simwiring.MERCHANT_VPA, Money.rupees("168"),
                                 "charging session", 0.95, "rule"),
            payer_vpa=simwiring.USER_VPA, idempotency_key="chg-1",
            umn=self.mandate.umn, order=self.order, quantity="11.2",
            agent_id=self.sim.agent_name,
        )
        self.assertTrue(result.ok, result.verdict.reasons)
        self.assertEqual(result.txn.amount, Money.rupees("168"))

    def test_the_books_still_balance(self):
        self.sim.orchestrator.execute(
            intent=PaymentIntent(True, simwiring.MERCHANT_VPA, Money.rupees("168"),
                                 "charging session", 0.95, "rule"),
            payer_vpa=simwiring.USER_VPA, idempotency_key="chg-1",
            umn=self.mandate.umn, order=self.order, quantity="11.2",
        )
        self.assertTrue(self.sim.reconciler.audit()["healthy"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
