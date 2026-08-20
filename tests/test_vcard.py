"""
Tests for the agent virtual card.

These do not test that the card works. They test what the extra hop *costs*, so the
three claims in `src/vcard.py` are results rather than assertions in a docstring.

Run with:  python3 tests/test_vcard.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import vcard  # noqa: E402
from core import Money  # noqa: E402
from models import TxnState, utcnow  # noqa: E402
from rails import FaultConfig  # noqa: E402
import sim as simwiring  # noqa: E402


class CardCase(unittest.TestCase):

    def setUp(self):
        self.db = tempfile.mktemp(suffix=".db")
        self.sim = simwiring.build(db_path=self.db, fresh=True)
        self.seeded = simwiring.seed(self.sim)
        self.umn = self.seeded["mandate"]["umn"]

        # The mandate must name the CARD as payee, because that is who the user's
        # money actually goes to. This single line is consequence 1 in the module
        # docstring, made concrete.
        self.card = vcard.issue(self.sim, "fridge-restock",
                                simwiring.USER_VPA, self.umn)
        m = self.sim.store.get_mandate(self.umn)
        m.allowed_payees = [self.card.vpa]
        self.sim.store.save_mandate(m)

    def tearDown(self):
        self.sim.close()
        if os.path.exists(self.db):
            os.remove(self.db)

    def user_balance(self) -> Money:
        return self.sim.store.get_account_by_vpa(simwiring.USER_VPA).balance


class TestItWorks(CardCase):

    def test_load_then_spend_reaches_the_merchant(self):
        ld = vcard.load(self.sim, self.card, Money.rupees("499"), "k-load")
        self.assertTrue(ld.ok, ld.verdict.reasons)
        self.assertEqual(vcard.balance(self.sim, self.card), Money.rupees("499"))

        sp = vcard.spend(self.sim, self.card, simwiring.MERCHANT_VPA,
                         Money.rupees("499"), "k-spend",
                         load_txn_id=ld.txn.txn_id)
        self.assertTrue(sp.ok, sp.verdict.reasons)

        self.assertEqual(vcard.balance(self.sim, self.card), Money(0))
        merch = self.sim.store.get_account_by_vpa(simwiring.MERCHANT_VPA)
        self.assertEqual(merch.balance, Money.rupees("499"))

    def test_books_still_balance_across_both_legs(self):
        ld = vcard.load(self.sim, self.card, Money.rupees("499"), "k1")
        vcard.spend(self.sim, self.card, simwiring.MERCHANT_VPA,
                    Money.rupees("499"), "k2", load_txn_id=ld.txn.txn_id)
        audit = self.sim.reconciler.audit()
        self.assertEqual(audit["global_net_paise"], 0)
        self.assertEqual(audit["suspense_balance_paise"], 0)


class TestWhatTheHopCosts(CardCase):
    """The three consequences, each as a failing property of the design."""

    def test_1_merchant_scoping_stops_working(self):
        """
        The mandate says Brewhouse only. The agent loads against it, then pays
        CloudHost. Both legs are legitimate and the money reaches the wrong shop.
        """
        ld = vcard.load(self.sim, self.card, Money.rupees("499"), "k-load")
        self.assertTrue(ld.ok)

        sp = vcard.spend(self.sim, self.card, simwiring.SECOND_MERCHANT_VPA,
                         Money.rupees("499"), "k-spend",
                         load_txn_id=ld.txn.txn_id)
        self.assertTrue(sp.ok, "the card paid an out-of-scope merchant")

        other = self.sim.store.get_account_by_vpa(simwiring.SECOND_MERCHANT_VPA)
        self.assertEqual(other.balance, Money.rupees("499"))

        # and for contrast: paying CloudHost directly off the mandate is refused
        direct = self.sim.policy.evaluate(
            __import__("models").PaymentIntent(
                True, simwiring.SECOND_MERCHANT_VPA, Money.rupees("499"),
                "direct", 0.95, "test"),
            simwiring.USER_VPA, self.sim.store.get_mandate(self.umn),
        )
        self.assertFalse(direct.allowed,
                         "direct payment to the same merchant should be refused")

    def test_2_failed_spend_strands_the_float(self):
        """
        Load works, spend fails. The money has left the user and not reached the
        merchant, and no reconciliation sweep finds it -- because nothing is stuck
        mid-transaction. It is simply sitting on the card.
        """
        opening = self.user_balance()
        ld = vcard.load(self.sim, self.card, Money.rupees("499"), "k-load")
        self.assertTrue(ld.ok)

        self.sim.faults.force = "credit_fail"
        sp = vcard.spend(self.sim, self.card, simwiring.MERCHANT_VPA,
                         Money.rupees("499"), "k-spend", load_txn_id=ld.txn.txn_id)
        self.assertFalse(sp.ok or sp.txn.state is TxnState.SETTLED)

        self.assertEqual(vcard.balance(self.sim, self.card), Money.rupees("499"))
        self.assertEqual(self.user_balance(), opening - Money.rupees("499"))

        swept = self.sim.reconciler.sweep()
        self.assertEqual(vcard.balance(self.sim, self.card), Money.rupees("499"),
                         "the recon sweep does not look at card float")

        # it takes a deliberate sweep of the card to give it back
        back = vcard.sweep(self.sim, self.card, "k-return")
        self.assertTrue(back.ok)
        self.assertEqual(vcard.balance(self.sim, self.card), Money(0))
        self.assertEqual(self.user_balance(), opening)

    def test_3_the_rails_cannot_link_a_spend_to_its_load(self):
        ld = vcard.load(self.sim, self.card, Money.rupees("499"), "k-load")
        vcard.spend(self.sim, self.card, simwiring.MERCHANT_VPA,
                    Money.rupees("499"), "k-spend", load_txn_id=ld.txn.txn_id)

        t = vcard.trace(self.sim, self.card)
        self.assertEqual(len(t["loads"]), 1)
        self.assertEqual(len(t["spends"]), 1)
        # the link exists only because vcard.py kept it in memory
        self.assertTrue(t["spends"][0]["linked_to_a_load"])
        self.assertIn("unrelated transactions", t["from_rails"])

        # nothing in the load transaction itself names the merchant
        load_txn = self.sim.store.get_txn(ld.txn.txn_id)
        self.assertEqual(load_txn.payee_vpa, self.card.vpa)
        self.assertNotEqual(load_txn.payee_vpa, simwiring.MERCHANT_VPA)


class TestFloatBehaviour(CardCase):

    def test_partial_spend_leaves_residual_float(self):
        """Load Rs 600, spend Rs 499, and Rs 101 of the user's money stays put."""
        ld = vcard.load(self.sim, self.card, Money.rupees("600"), "k-load")
        vcard.spend(self.sim, self.card, simwiring.MERCHANT_VPA,
                    Money.rupees("499"), "k-spend", load_txn_id=ld.txn.txn_id)
        self.assertEqual(vcard.balance(self.sim, self.card), Money.rupees("101"))

    def test_mandate_headroom_is_consumed_by_the_load_not_the_spend(self):
        """
        The user's cap is spent the moment the card is funded, whether or not the
        purchase ever happens. Loading Rs 600 for a Rs 499 purchase burns Rs 600.
        """
        before = self.sim.store.get_mandate(self.umn).remaining
        vcard.load(self.sim, self.card, Money.rupees("600"), "k-load")
        after = self.sim.store.get_mandate(self.umn).remaining
        self.assertEqual(before - after, Money.rupees("600"))

    def test_sweep_is_a_no_op_on_an_empty_card(self):
        self.assertIsNone(vcard.sweep(self.sim, self.card, "k-none"))

    def test_refund_releases_the_headroom_it_consumed(self):
        """
        A purchase that never happened must not keep eating the cap.

        The load consumes headroom. If the spend then fails and the money is
        returned, the user is whole in cash -- but a run of failures would silently
        exhaust the mandate unless the headroom comes back too.
        """
        before = self.sim.store.get_mandate(self.umn).remaining
        vcard.load(self.sim, self.card, Money.rupees("499"), "k-load")
        self.assertEqual(self.sim.store.get_mandate(self.umn).remaining,
                         before - Money.rupees("499"))

        self.sim.faults.force = "credit_fail"
        vcard.spend(self.sim, self.card, simwiring.MERCHANT_VPA,
                    Money.rupees("499"), "k-spend")
        vcard.sweep(self.sim, self.card, "k-refund")

        self.assertEqual(vcard.balance(self.sim, self.card), Money(0))
        self.assertEqual(self.sim.store.get_mandate(self.umn).remaining, before,
                         "headroom must return with the money")


if __name__ == "__main__":
    unittest.main(verbosity=2)
