"""
Tests for the cross rail receipt.

`test_vcard.py` proves the audit chain is severed. The load names the card and
never the merchant, so the ledger cannot reconstruct who bought what from whom.
These tests are the other side of that. They pin down what a receipt proves once
it exists, and what it still does not.

The property that matters most is the last one in this file. A stranger holding no
private key at all can check the whole thing. If that were not true the receipt
would only be evidence to the party that wrote it, which is not evidence.

Run with:  python3 tests/test_receipt.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import receipt as rcpt  # noqa: E402
import vcard  # noqa: E402
from consent import Order, OrderSigner  # noqa: E402
from core import Money  # noqa: E402
from identity import PublicKey, Resolver, Signer  # noqa: E402
from models import utcnow  # noqa: E402
from policy import PolicyConfig  # noqa: E402
import sim as simwiring  # noqa: E402


class ReceiptCase(unittest.TestCase):
    """A card funded purchase. Rs 403 of groceries, loaded then spent."""

    def setUp(self):
        self.db = tempfile.mktemp(suffix=".db")
        self.sim = simwiring.build(db_path=self.db, fresh=True,
                                   policy_config=PolicyConfig(require_order=False))
        simwiring.seed(self.sim)
        now = utcnow()

        self.card = vcard.issue(self.sim, self.sim.agent_name,
                                simwiring.USER_VPA, umn="")
        self.mandate = self.sim.orchestrator.create_mandate(
            payer_vpa=simwiring.USER_VPA, allowed_payees=[self.card.vpa],
            max_amount_per_txn=Money.rupees("2000"),
            total_cap=Money.rupees("10000"),
            valid_from=now - timedelta(minutes=1),
            valid_until=now + timedelta(days=90),
            purpose="card funding", agent_id=self.sim.agent_name,
        )
        self.card.umn = self.mandate.umn

        self.order = Order.build("ORD-1", simwiring.MERCHANT_VPA,
                                 [("Atta 5kg", "275"), ("Milk 1L", "128")])
        self.order.sign(OrderSigner.AGENT, self.sim.agent_key,
                        self.sim.merchant_keys[simwiring.MERCHANT_VPA])

    def tearDown(self):
        self.sim.close()
        if os.path.exists(self.db):
            os.remove(self.db)

    # -- helpers -----------------------------------------------------------

    def operator(self):
        """The owner issues receipts here. It is already in the resolver."""
        return self.sim.owner_key

    def completed(self):
        ld = vcard.load(self.sim, self.card, self.order.total, "L1")
        sp = vcard.spend(self.sim, self.card, simwiring.MERCHANT_VPA,
                         self.order.total, "S1", order=self.order,
                         load_txn_id=ld.txn.txn_id)
        return rcpt.for_card(self.sim, self.card, self.order,
                             ld.txn.txn_id, sp.txn.txn_id).sign_with(self.operator())

    def verify(self, receipt, **kw):
        return rcpt.verify(receipt, self.sim.resolver, self.sim.registry, **kw)

    def named(self, checks, name):
        return next(c for c in checks if c["check"] == name)


# --------------------------------------------------------------------------
# It records what happened
# --------------------------------------------------------------------------

class TestACompletedPurchase(ReceiptCase):

    def test_it_verifies(self):
        ok, why, _ = self.verify(self.completed())
        self.assertTrue(ok, why)

    def test_the_outcome_is_settled(self):
        self.assertEqual(self.completed().outcome, rcpt.Outcome.SETTLED)

    def test_the_money_adds_up(self):
        r = self.completed()
        self.assertEqual(r.left_the_user, Money.rupees("403"))
        self.assertEqual(r.reached_the_merchant, Money.rupees("403"))
        self.assertEqual(r.came_back, Money.zero())
        self.assertEqual(r.unaccounted, Money.zero())

    def test_it_spans_both_rails(self):
        rails = {leg.rail for leg in self.completed().legs}
        self.assertEqual(rails, {rcpt.Rail.UPI, rcpt.Rail.CARD})

    def test_the_id_is_a_hash_of_the_content(self):
        r = self.completed()
        before = r.id
        r.outcome = "something else"
        self.assertNotEqual(r.id, before)


class TestTheChainIsClosed(ReceiptCase):
    """The severed audit chain from test_vcard.py, joined back up."""

    def test_a_spend_is_traced_to_the_load_that_funded_it(self):
        r = self.completed()
        _ok, _why, checks = self.verify(r)
        chain = [c for c in checks if c["check"].startswith("spend_chains_to_a_load")]
        self.assertEqual(len(chain), 1)
        self.assertTrue(chain[0]["passed"])

    def test_a_spend_with_no_load_behind_it_is_refused(self):
        """Two unrelated transactions in one receipt do not make a chain."""
        r = self.completed()
        r.legs = tuple(l for l in r.legs if l.kind != rcpt.LegKind.LOAD)
        r.sign_with(self.operator())
        ok, why, _ = self.verify(r)
        self.assertFalse(ok)
        self.assertTrue(any("chain is broken" in w for w in why))


# --------------------------------------------------------------------------
# It catches what the rails cannot
# --------------------------------------------------------------------------

class TestStrandedFloat(ReceiptCase):
    """recon.py cannot see this. Nothing is stuck mid transaction."""

    def stranded(self):
        ld = vcard.load(self.sim, self.card, Money.rupees("600"), "L1")
        self.sim.faults.force = "credit_fail"
        sp = vcard.spend(self.sim, self.card, simwiring.MERCHANT_VPA,
                         self.order.total, "S1", order=self.order,
                         load_txn_id=ld.txn.txn_id)
        return rcpt.for_card(self.sim, self.card, self.order, ld.txn.txn_id,
                             sp.txn.txn_id if sp.txn else None).sign_with(self.operator())

    def test_the_reconciliation_sweep_reports_healthy_books(self):
        """The books really are balanced. The user is still out of pocket."""
        self.stranded()
        self.assertTrue(self.sim.reconciler.audit()["healthy"])

    def test_the_receipt_names_the_missing_money(self):
        r = self.stranded()
        self.assertEqual(r.unaccounted, Money.rupees("600"))
        self.assertEqual(r.outcome, rcpt.Outcome.STRANDED)

    def test_it_refuses_to_verify(self):
        ok, why, checks = self.verify(self.stranded())
        self.assertFalse(ok)
        self.assertFalse(self.named(checks, "nothing_unaccounted")["passed"])


class TestARefundedPurchase(ReceiptCase):
    """A purchase that did not happen is a real outcome and must be provable."""

    def refunded(self):
        ld = vcard.load(self.sim, self.card, Money.rupees("600"), "L1")
        sw = vcard.sweep(self.sim, self.card, "W1")
        return rcpt.for_card(self.sim, self.card, self.order, ld.txn.txn_id,
                             None, sw.txn.txn_id).sign_with(self.operator())

    def test_it_verifies(self):
        ok, why, _ = self.verify(self.refunded())
        self.assertTrue(ok, why)

    def test_the_outcome_is_returned(self):
        self.assertEqual(self.refunded().outcome, rcpt.Outcome.RETURNED)

    def test_everything_that_left_came_back(self):
        r = self.refunded()
        self.assertEqual(r.came_back, r.left_the_user)
        self.assertEqual(r.unaccounted, Money.zero())

    def test_claiming_a_refund_while_paying_the_merchant_is_refused(self):
        r = self.completed()
        r.outcome = rcpt.Outcome.RETURNED
        r.sign_with(self.operator())
        ok, why, _ = self.verify(r)
        self.assertFalse(ok)
        self.assertTrue(any("reached the merchant" in w for w in why))


# --------------------------------------------------------------------------
# Tampering
# --------------------------------------------------------------------------

class TestTampering(ReceiptCase):

    def test_an_unsigned_receipt_verifies_nothing(self):
        r = self.completed()
        r.token = ""
        ok, why, _ = self.verify(r)
        self.assertFalse(ok)
        self.assertIn("does not verify", " ".join(why))

    def test_rewriting_the_outcome_is_caught(self):
        r = self.completed()
        r.outcome = "settled, honestly"
        ok, why, checks = self.verify(r)
        self.assertFalse(ok)
        self.assertFalse(self.named(checks, "receipt_unaltered")["passed"])

    def test_rewriting_a_leg_amount_is_caught(self):
        r = self.completed()
        first = r.legs[0]
        r.legs = (rcpt.Leg(kind=first.kind, rail=first.rail, txn_id=first.txn_id,
                           payer=first.payer, payee=first.payee,
                           amount=Money.rupees("50000"), state=first.state,
                           rrn=first.rrn),) + r.legs[1:]
        ok, _why, checks = self.verify(r)
        self.assertFalse(ok)
        self.assertFalse(self.named(checks, "receipt_unaltered")["passed"])

    def test_a_receipt_from_an_unknown_issuer_is_refused(self):
        r = self.completed().sign_with(Signer("nobody:in:particular"))
        ok, why, _ = self.verify(r)
        self.assertFalse(ok)
        self.assertIn("does not verify", " ".join(why))

    def test_a_forged_order_signature_is_caught(self):
        r = self.completed()
        r.order.signatures[self.sim.agent_name] = b"\x00" * 64
        r.sign_with(self.operator())
        ok, why, _ = self.verify(r)
        self.assertFalse(ok)
        self.assertTrue(any("order signature" in w for w in why))


# --------------------------------------------------------------------------
# The agent behind it
# --------------------------------------------------------------------------

class TestTheAgent(ReceiptCase):

    def test_a_revoked_agent_invalidates_the_receipt(self):
        r = self.completed()
        self.assertTrue(self.verify(r)[0])
        self.sim.registry.revoke_agent(self.sim.agent_name)
        ok, why, _ = self.verify(r)
        self.assertFalse(ok)
        self.assertTrue(any("revoked" in w for w in why))

    def test_a_registration_for_a_different_agent_is_caught(self):
        other = self.sim.registry.register_agent(
            Signer("agent:fuel"), device_id=simwiring.DEVICE_ID, agent_id="agent:fuel")
        r = self.completed()
        r.registration_token = other.token
        r.sign_with(self.operator())
        ok, why, checks = self.verify(r)
        self.assertFalse(ok)
        self.assertFalse(self.named(checks, "registration_names_this_agent")["passed"])


# --------------------------------------------------------------------------
# Metered purchases
# --------------------------------------------------------------------------

class TestMeteredReceipt(ReceiptCase):

    def metered(self, billed):
        order = Order.metered("CHG-1", simwiring.MERCHANT_VPA, "Charging session",
                              rate="15", unit="kWh", cap="250")
        order.sign(OrderSigner.AGENT, self.sim.agent_key,
                   self.sim.merchant_keys[simwiring.MERCHANT_VPA])
        ld = vcard.load(self.sim, self.card, Money.rupees(billed), "L1")
        sp = vcard.spend(self.sim, self.card, simwiring.MERCHANT_VPA,
                         Money.rupees(billed), "S1", load_txn_id=ld.txn.txn_id)
        return rcpt.for_card(self.sim, self.card, order, ld.txn.txn_id,
                             sp.txn.txn_id).sign_with(self.operator())

    def test_a_session_reconciles_against_the_meter_reading(self):
        ok, why, _ = self.verify(self.metered("168"), quantity="11.2")
        self.assertTrue(ok, why)

    def test_a_reading_that_does_not_match_the_amount_is_refused(self):
        ok, why, _ = self.verify(self.metered("168"), quantity="20")
        self.assertFalse(ok)
        self.assertTrue(any("order was" in w for w in why))


# --------------------------------------------------------------------------
# The property the whole artifact rests on
# --------------------------------------------------------------------------

class TestAThirdPartyCanCheckIt(ReceiptCase):

    def stranger_resolver(self) -> Resolver:
        """Everything a dispute referee would have. Public keys and nothing else."""
        out = Resolver()
        for name in (self.sim.agent_name, simwiring.MERCHANT_VPA,
                     self.sim.owner_key.label):
            key = self.sim.resolver.resolve(name)
            out.register(name, PublicKey(raw=key.raw, label=name))
        return out

    def test_a_stranger_holding_no_private_key_can_verify(self):
        resolver = self.stranger_resolver()
        for key in resolver._keys.values():
            self.assertIsInstance(key, PublicKey)
            self.assertFalse(hasattr(key, "sign"))

        ok, why, _ = rcpt.verify(self.completed(), resolver, None)
        self.assertTrue(ok, why)

    def test_that_stranger_still_catches_tampering(self):
        r = self.completed()
        r.outcome = "settled, honestly"
        ok, _why, _ = rcpt.verify(r, self.stranger_resolver(), None)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
