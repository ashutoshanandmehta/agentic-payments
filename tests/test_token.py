"""
Tests for the card rail.

`test_vcard.py` measures what funding an agent over UPI costs. Merchant scope stops
working, float strands, the audit chain is severed. These tests exist to show those
are not costs of using an agent. They are costs of the only shape UPI can express.

On cards a token is issued. It is a reference and not a purse, the network validates
its scope at every authorisation, and the money moves once. None of the three costs
arise, because the thing that causes them never happens.

The last class puts the two rails side by side on the same purchase.

Run with:  python3 tests/test_token.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import agentic_token as tok  # noqa: E402
import vcard  # noqa: E402
from consent import Order, OrderSigner  # noqa: E402
from core import Money  # noqa: E402
from models import utcnow  # noqa: E402
import sim as simwiring  # noqa: E402


class TokenCase(unittest.TestCase):
    """A token scoped to one shop and one category, on the owner's card."""

    def setUp(self):
        self.db = tempfile.mktemp(suffix=".db")
        self.sim = simwiring.build(db_path=self.db, fresh=True)
        simwiring.seed(self.sim)
        self.token = tok.issue(
            self.sim, self.sim.agent_name, simwiring.USER_VPA,
            simwiring.USER_CARD_VPA,
            per_txn_cap=Money.rupees("2000"), total_cap=Money.rupees("5000"),
            allowed_merchants=[simwiring.MERCHANT_VPA],
            allowed_categories=["groceries"],
        )

    def tearDown(self):
        self.sim.close()
        if os.path.exists(self.db):
            os.remove(self.db)

    def balance(self, vpa):
        return self.sim.store.get_account_by_vpa(vpa).balance

    def order(self, total="403", merchant=None, category="groceries"):
        o = Order.build("ORD-1", merchant or simwiring.MERCHANT_VPA,
                        [("Basket", total)], category=category)
        o.sign(OrderSigner.AGENT, self.sim.agent_key,
               self.sim.merchant_keys[o.payee_vpa])
        return o

    def scope(self, merchant=None, amount="403", category="groceries"):
        return tok.validate_scope(
            self.token, merchant or simwiring.MERCHANT_VPA,
            Money.rupees(amount), category=category)


# --------------------------------------------------------------------------
# A token is a reference, not a purse
# --------------------------------------------------------------------------

class TestATokenHoldsNoValue(TokenCase):

    def test_issuing_moves_no_money(self):
        before = self.balance(simwiring.USER_CARD_VPA)
        tok.issue(self.sim, "agent:second", simwiring.USER_VPA,
                  simwiring.USER_CARD_VPA,
                  per_txn_cap=Money.rupees("100"), total_cap=Money.rupees("500"))
        self.assertEqual(self.balance(simwiring.USER_CARD_VPA), before)

    def test_it_says_so_itself(self):
        self.assertFalse(self.token.holds_value)

    def test_no_account_is_created_for_it(self):
        """The UPI path needs a real account for the card. This does not."""
        self.assertIsNone(
            self.sim.store.get_account_by_vpa_safe(self.token.token_id))

    def test_it_never_holds_float(self):
        self.assertEqual(tok.float_held(self.sim, self.token), Money.zero())
        tok.authorise(self.sim, self.token, simwiring.MERCHANT_VPA,
                      Money.rupees("403"), "A1", order=self.order())
        self.assertEqual(tok.float_held(self.sim, self.token), Money.zero())

    def test_issuing_against_an_unknown_card_is_refused(self):
        with self.assertRaises(ValueError):
            tok.issue(self.sim, "agent:x", simwiring.USER_VPA, "nobody@nowhere",
                      per_txn_cap=Money.rupees("100"),
                      total_cap=Money.rupees("500"))


# --------------------------------------------------------------------------
# The network checks the scope at every authorisation
# --------------------------------------------------------------------------

class TestScopeValidation(TokenCase):

    def test_an_in_scope_payment_passes(self):
        ok, why, _ = self.scope()
        self.assertTrue(ok, why)

    def test_a_merchant_outside_the_scope_is_refused(self):
        ok, why, _ = self.scope(merchant=simwiring.SECOND_MERCHANT_VPA)
        self.assertFalse(ok)
        self.assertIn("outside the merchants", " ".join(why))

    def test_a_category_outside_the_scope_is_refused(self):
        ok, why, _ = self.scope(category="fuel")
        self.assertFalse(ok)
        self.assertIn("outside the categories", " ".join(why))

    def test_over_the_per_payment_cap_is_refused(self):
        ok, why, _ = self.scope(amount="3000")
        self.assertFalse(ok)
        self.assertIn("per payment cap", " ".join(why))

    def test_over_the_remaining_total_is_refused(self):
        self.token.consumed = Money.rupees("4900")
        ok, why, _ = self.scope(amount="200")
        self.assertFalse(ok)
        self.assertIn("left on this token", " ".join(why))

    def test_an_expired_token_is_refused(self):
        self.token.expires_at = utcnow() - timedelta(days=1)
        ok, why, _ = self.scope()
        self.assertFalse(ok)
        self.assertIn("expired", " ".join(why))

    def test_a_token_with_no_merchant_list_accepts_any_merchant(self):
        open_token = tok.issue(
            self.sim, "agent:open", simwiring.USER_VPA, simwiring.USER_CARD_VPA,
            per_txn_cap=Money.rupees("2000"), total_cap=Money.rupees("5000"))
        ok, why, _ = tok.validate_scope(open_token, simwiring.SECOND_MERCHANT_VPA,
                                        Money.rupees("100"))
        self.assertTrue(ok, why)

    def test_the_check_runs_before_any_money_moves(self):
        before = self.balance(simwiring.USER_CARD_VPA)
        result = tok.authorise(self.sim, self.token, simwiring.SECOND_MERCHANT_VPA,
                               Money.rupees("403"), "A1")
        self.assertFalse(result.ok)
        self.assertIsNone(result.txn)
        self.assertEqual(self.balance(simwiring.USER_CARD_VPA), before)


# --------------------------------------------------------------------------
# Paying
# --------------------------------------------------------------------------

class TestAuthorising(TokenCase):

    def test_the_money_moves_once_owner_to_merchant(self):
        card_before = self.balance(simwiring.USER_CARD_VPA)
        result = tok.authorise(self.sim, self.token, simwiring.MERCHANT_VPA,
                               Money.rupees("403"), "A1", order=self.order())

        self.assertTrue(result.ok, result.verdict.reasons)
        self.assertEqual(self.balance(simwiring.USER_CARD_VPA),
                         card_before - Money.rupees("403"))
        self.assertEqual(self.balance(simwiring.MERCHANT_VPA), Money.rupees("403"))

    def test_it_is_one_transaction_not_two(self):
        result = tok.authorise(self.sim, self.token, simwiring.MERCHANT_VPA,
                               Money.rupees("403"), "A1", order=self.order())
        related = [t for t in self.sim.store.list_txns(limit=50)
                   if t.agent_id == self.sim.agent_name]
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0].txn_id, result.txn.txn_id)

    def test_the_agent_is_named_on_the_transaction(self):
        result = tok.authorise(self.sim, self.token, simwiring.MERCHANT_VPA,
                               Money.rupees("403"), "A1", order=self.order())
        self.assertEqual(result.txn.agent_id, self.sim.agent_name)

    def test_spending_consumes_the_token(self):
        tok.authorise(self.sim, self.token, simwiring.MERCHANT_VPA,
                      Money.rupees("403"), "A1", order=self.order())
        self.assertEqual(self.token.consumed, Money.rupees("403"))
        self.assertEqual(self.token.remaining, Money.rupees("4597"))

    def test_the_books_balance(self):
        tok.authorise(self.sim, self.token, simwiring.MERCHANT_VPA,
                      Money.rupees("403"), "A1", order=self.order())
        self.assertTrue(self.sim.reconciler.audit()["healthy"])


class TestRevoking(TokenCase):

    def test_revoking_is_one_action(self):
        tok.revoke(self.sim, self.token)
        self.assertEqual(self.token.status, tok.TokenStatus.REVOKED)

    def test_a_revoked_token_cannot_authorise(self):
        tok.revoke(self.sim, self.token)
        result = tok.authorise(self.sim, self.token, simwiring.MERCHANT_VPA,
                               Money.rupees("100"), "A1")
        self.assertFalse(result.ok)
        self.assertIn("revoked", " ".join(result.verdict.reasons))

    def test_there_is_no_float_to_return(self):
        """The UPI path has to sweep. This has nothing to sweep."""
        tok.authorise(self.sim, self.token, simwiring.MERCHANT_VPA,
                      Money.rupees("403"), "A1", order=self.order())
        tok.revoke(self.sim, self.token)
        self.assertEqual(tok.float_held(self.sim, self.token), Money.zero())


# --------------------------------------------------------------------------
# The two rails on the same purchase
# --------------------------------------------------------------------------

class TestTheRailsDiffer(TokenCase):
    """Same owner, same shop, same basket. Two very different shapes."""

    def upi_funded_agent(self):
        now = utcnow()
        card = vcard.issue(self.sim, "agent:upi", simwiring.USER_VPA, umn="")
        m = self.sim.orchestrator.create_mandate(
            payer_vpa=simwiring.USER_VPA, allowed_payees=[card.vpa],
            max_amount_per_txn=Money.rupees("2000"),
            total_cap=Money.rupees("5000"),
            valid_from=now - timedelta(minutes=1),
            valid_until=now + timedelta(days=90),
            purpose="agent funding", agent_id="agent:upi",
        )
        card.umn = m.umn
        return card

    def test_upi_needs_two_transactions_and_the_card_needs_one(self):
        card = self.upi_funded_agent()
        load = vcard.load(self.sim, card, Money.rupees("403"), "L1")
        spend = vcard.spend(self.sim, card, simwiring.MERCHANT_VPA,
                            Money.rupees("403"), "S1")
        self.assertTrue(load.ok and spend.ok)

        token_result = tok.authorise(self.sim, self.token, simwiring.MERCHANT_VPA,
                                     Money.rupees("511"), "A1",
                                     order=self.order(total="511"))
        self.assertTrue(token_result.ok, token_result.verdict.reasons)

        upi_legs = len([t for t in self.sim.store.list_txns(limit=50)
                        if t.agent_id == "agent:upi"])
        card_legs = len([t for t in self.sim.store.list_txns(limit=50)
                         if t.agent_id == self.sim.agent_name])
        self.assertEqual(upi_legs, 2)
        self.assertEqual(card_legs, 1)

    def test_upi_loses_merchant_scope_and_the_token_keeps_it(self):
        """The same out of scope payment. One rail stops it, the other does not."""
        card = self.upi_funded_agent()
        vcard.load(self.sim, card, Money.rupees("403"), "L1")
        loose = vcard.spend(self.sim, card, simwiring.SECOND_MERCHANT_VPA,
                            Money.rupees("403"), "S1")
        self.assertTrue(loose.ok, "UPI funding cannot hold merchant scope")

        scoped = tok.authorise(self.sim, self.token, simwiring.SECOND_MERCHANT_VPA,
                               Money.rupees("403"), "A1")
        self.assertFalse(scoped.ok, "the network validates scope every time")

    def test_only_the_upi_path_can_strand_float(self):
        card = self.upi_funded_agent()
        vcard.load(self.sim, card, Money.rupees("600"), "L1")
        self.sim.faults.force = "credit_fail"
        vcard.spend(self.sim, card, simwiring.MERCHANT_VPA,
                    Money.rupees("403"), "S1")

        self.assertEqual(vcard.balance(self.sim, card), Money.rupees("600"))
        self.assertEqual(tok.float_held(self.sim, self.token), Money.zero())


if __name__ == "__main__":
    unittest.main(verbosity=2)
