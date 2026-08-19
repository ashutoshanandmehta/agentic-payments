"""
Tests for the order gate.

The rest of the suite defends the rails: money cannot be created, destroyed,
double-spent or stranded. These defend something the rails cannot see -- whether the
payment matches what the user actually agreed to buy.

Run with:  python3 tests/test_consent.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from consent import Keypair, Order, OrderSigner, validate_order  # noqa: E402
from core import Money  # noqa: E402
from models import PaymentIntent, utcnow  # noqa: E402
from policy import PolicyConfig  # noqa: E402
import sim as simwiring  # noqa: E402


def intent(amount="118", payee=None, confidence=0.95) -> PaymentIntent:
    return PaymentIntent(
        should_pay=True,
        payee_vpa=payee or simwiring.MERCHANT_VPA,
        amount=Money.rupees(str(amount)),
        reason="monthly invoice",
        confidence=confidence,
        source="rule",
    )


class ConsentCase(unittest.TestCase):
    """A simulator with the order gate switched on."""

    signer = OrderSigner.AGENT

    def setUp(self):
        self.db = tempfile.mktemp(suffix=".db")
        self.sim = simwiring.build(
            db_path=self.db, fresh=True,
            policy_config=PolicyConfig(require_order=True),
            order_signer=self.signer,
        )
        self.seeded = simwiring.seed(self.sim)
        self.umn = self.seeded["mandate"]["umn"]

    def tearDown(self):
        self.sim.close()
        if os.path.exists(self.db):
            os.remove(self.db)

    # -- helpers ---------------------------------------------------------

    def order(self, lines=None, total=None, payee=None, **kw) -> Order:
        o = Order.build(
            order_id=kw.pop("order_id", "ORD-1"),
            payee_vpa=payee or simwiring.MERCHANT_VPA,
            lines=lines or [("Monthly plan", "99"), ("GST", "19")],
            total=total, **kw,
        )
        return o.sign(self.signer, self.sim.agent_key,
                      self.sim.merchant_keys[o.payee_vpa])

    def verdict(self, order, amount="118", payee=None):
        return self.sim.policy.evaluate(
            intent(amount, payee), simwiring.USER_VPA,
            self.sim.store.get_mandate(self.umn), order,
        )

    def named(self, v, name):
        return next(c for c in v.checks if c["check"] == name)


class TestOrderGate(ConsentCase):

    def test_matching_payment_passes(self):
        """Order for Rs 118, payment of Rs 118, same payee."""
        v = self.verdict(self.order())
        self.assertTrue(v.allowed, v.reasons)

    def test_no_order_is_refused(self):
        """With the gate on, a payment with nothing to check against fails."""
        v = self.verdict(None)
        self.assertFalse(v.allowed)
        self.assertTrue(any("nothing records" in r for r in v.reasons))

    def test_price_drift_is_caught(self):
        """User agreed Rs 118; the debit is Rs 162, still under every limit."""
        v = self.verdict(self.order(), amount="162")
        self.assertFalse(v.allowed)
        self.assertFalse(self.named(v, "amount_matches_order")["passed"])

    def test_payee_substitution_is_caught(self):
        """Order agreed with Brewhouse, money routed to CloudHost."""
        v = self.verdict(self.order(), payee=simwiring.SECOND_MERCHANT_VPA)
        self.assertFalse(v.allowed)
        self.assertFalse(self.named(v, "payee_matches_order")["passed"])

    def test_inconsistent_order_is_caught(self):
        """Lines add to Rs 118 but the order claims Rs 300."""
        v = self.verdict(self.order(total="300"), amount="300")
        self.assertFalse(v.allowed)
        self.assertFalse(self.named(v, "order_self_consistent")["passed"])

    def test_stale_order_is_refused(self):
        """An order agreed two hours ago is past its 30-minute life."""
        old = self.order(agreed_at=utcnow() - timedelta(hours=2))
        v = self.verdict(old)
        self.assertFalse(v.allowed)
        self.assertFalse(self.named(v, "order_fresh")["passed"])

    def test_unsigned_order_is_refused(self):
        o = Order.build("ORD-X", simwiring.MERCHANT_VPA, [("Monthly plan", "118")])
        v = self.verdict(o)
        self.assertFalse(v.allowed)

    def test_tampering_breaks_the_signature(self):
        """Raise the total after signing, without the signer's key."""
        o = self.order()
        forged = o.tamper(total=Money.rupees("600"))
        v = self.verdict(forged, amount="600")
        self.assertFalse(v.allowed)
        self.assertFalse(self.named(v, "order_signed_by_agent")["passed"])

    def test_gate_off_lets_the_overcharge_through(self):
        """
        The comparison that makes the point: without the order gate, the mandate and
        policy both pass a Rs 600 charge, because neither knows about the Rs 118
        basket. This is UPI's behaviour today.
        """
        self.sim.policy.config.require_order = False
        v = self.sim.policy.evaluate(
            intent("600"), simwiring.USER_VPA,
            self.sim.store.get_mandate(self.umn), None,
        )
        self.assertTrue(v.allowed, v.reasons)


class TestWhoSignsTheOrder(ConsentCase):
    """
    The open question, run as an experiment.

    A *self-consistent* inflated order -- lines that really do add to Rs 600 -- is
    approved under every signing arrangement. A signature says who wrote a record. It
    does not say the record is true, and once the order is the only surviving evidence
    of the agreement there is nothing left to compare it against.
    """

    def _consistent_lie(self, signer):
        self.signer = signer
        self.setUp()
        o = self.order(lines=[("Monthly plan", "300"), ("Add-on", "300")])
        return self.verdict(o, amount="600")

    def test_agent_signature_does_not_stop_it(self):
        self.assertTrue(self._consistent_lie(OrderSigner.AGENT).allowed)

    def test_merchant_signature_does_not_stop_it(self):
        self.assertTrue(self._consistent_lie(OrderSigner.MERCHANT).allowed)

    def test_both_signatures_do_not_stop_it(self):
        self.assertTrue(self._consistent_lie(OrderSigner.BOTH).allowed)

    def test_a_tight_mandate_ceiling_does_stop_it(self):
        """What actually refuses it: a per-transaction cap near the real basket."""
        self.signer = OrderSigner.BOTH
        self.setUp()
        m = self.sim.store.get_mandate(self.umn)
        m.max_amount_per_txn = Money.rupees("150")
        self.sim.store.save_mandate(m)
        o = self.order(lines=[("Monthly plan", "300"), ("Add-on", "300")])
        v = self.verdict(o, amount="600")
        self.assertFalse(v.allowed)
        self.assertFalse(self.named(v, "under_per_txn_cap")["passed"])

    def test_requiring_both_stops_everything_if_the_shop_abstains(self):
        """
        The realistic cost of requiring two signatures. No merchant integrates with a
        scheme that does not exist yet, so demanding their signature refuses every
        payment -- including the honest ones.
        """
        self.signer = OrderSigner.BOTH
        self.setUp()
        o = Order.build("ORD-1", simwiring.MERCHANT_VPA,
                        [("Monthly plan", "99"), ("GST", "19")])
        o.sign(OrderSigner.AGENT, self.sim.agent_key,
               self.sim.merchant_keys[simwiring.MERCHANT_VPA])
        v = self.verdict(o)
        self.assertFalse(v.allowed)
        self.assertFalse(self.named(v, "order_signed_by_merchant")["passed"])


class TestEndToEnd(ConsentCase):

    def test_matching_order_settles_and_books_balance(self):
        r = self.sim.orchestrator.execute(
            intent=intent("118"), payer_vpa=simwiring.USER_VPA,
            idempotency_key="k-ok", umn=self.umn, order=self.order(),
        )
        self.assertTrue(r.ok, r.verdict.reasons)
        audit = self.sim.reconciler.audit()
        self.assertEqual(audit["global_net_paise"], 0)
        self.assertEqual(audit["suspense_balance_paise"], 0)

    def test_drifted_order_never_reaches_the_rails(self):
        r = self.sim.orchestrator.execute(
            intent=intent("162"), payer_vpa=simwiring.USER_VPA,
            idempotency_key="k-drift", umn=self.umn, order=self.order(),
        )
        self.assertFalse(r.ok)
        user = self.sim.store.get_account_by_vpa(simwiring.USER_VPA)
        self.assertEqual(user.balance, Money.rupees("10000"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
