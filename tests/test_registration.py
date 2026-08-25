"""
Tests for agent identity and registration.

`test_sim.py` defends the rails and `test_consent.py` defends the order gate.
These defend a claim neither of them makes: that somebody holding **no private
key** can check who an agent is and whether it is still allowed to act.

That matters because a receipt nobody else can verify is not evidence. If checking
a signature needs the secret that made it, the only party who can check it is the
party who could have forged it.

Run with:  python3 tests/test_registration.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core import Money  # noqa: E402
from identity import (  # noqa: E402
    PublicKey,
    Resolver,
    Signer,
    b58decode,
    b58encode,
    b64url_decode,
    decode_did_key,
    encode_did_key,
    jws_sign,
    jws_verify,
)
from models import PaymentIntent, utcnow  # noqa: E402
from registration import (  # noqa: E402
    MIN_STATUS_BITS,
    REGISTRATION_VCT,
    AgentRegistry,
    StatusList,
)
import sim as simwiring  # noqa: E402


# --------------------------------------------------------------------------
# did:key
# --------------------------------------------------------------------------

class TestDidKey(unittest.TestCase):
    """The identifier is the key. No registry, no lookup, no network."""

    #: from the did:key specification's own examples
    SPEC_VECTOR = "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK"

    def test_matches_the_spec_test_vector(self):
        """Our encoder agrees with the spec, not just with our decoder."""
        raw = decode_did_key(self.SPEC_VECTOR)
        self.assertEqual(len(raw), 32)
        self.assertEqual(encode_did_key(raw), self.SPEC_VECTOR)

    def test_base58_survives_leading_zeros(self):
        """Leading zero bytes are the classic base58 bug: they encode to '1's."""
        for blob in (b"\x00\x00\x01\x02", b"\x00", b"hello", bytes(range(32))):
            self.assertEqual(b58decode(b58encode(blob)), blob)

    def test_every_ed25519_did_shares_a_prefix(self):
        """The multicodec header is fixed, so 'z6Mk' is not a coincidence."""
        for i in range(5):
            self.assertTrue(Signer(f"a{i}").did.startswith("did:key:z6Mk"))

    def test_a_non_ed25519_multicodec_is_refused(self):
        with self.assertRaises(ValueError):
            decode_did_key("did:key:z" + b58encode(b"\xe7\x01" + bytes(32)))

    def test_malformed_dids_raise(self):
        for bad in ("", "did:web:example.com", "did:key:QQQ", "did:key:z0OIl"):
            with self.assertRaises(ValueError):
                decode_did_key(bad)


# --------------------------------------------------------------------------
# The split that makes evidence possible
# --------------------------------------------------------------------------

class TestPublicVerification(unittest.TestCase):
    """Verifying must never need the secret."""

    def setUp(self):
        self.signer = Signer("agent:coffee")
        self.blob = b"the cart says 118"
        self.sig = self.signer.sign(self.blob)

    def test_a_public_key_alone_verifies(self):
        detached = PublicKey.from_did(self.signer.did)
        self.assertTrue(detached.verify(self.blob, self.sig))

    def test_a_public_key_cannot_sign(self):
        """No route from the verifying half back to the signing half."""
        detached = PublicKey.from_did(self.signer.did)
        self.assertFalse(hasattr(detached, "sign"))
        self.assertFalse(hasattr(detached, "_private"))

    def test_tampering_is_caught(self):
        detached = PublicKey.from_did(self.signer.did)
        self.assertFalse(detached.verify(b"the cart says 600", self.sig))

    def test_another_key_does_not_verify(self):
        self.assertFalse(Signer("someone-else").public.verify(self.blob, self.sig))

    def test_the_policy_engine_holds_no_private_keys(self):
        """The gate is onboarded with public halves and could not forge one."""
        db = tempfile.mktemp(suffix=".db")
        sim = simwiring.build(db_path=db, fresh=True)
        try:
            keys = sim.policy.resolver._keys
            self.assertTrue(keys)
            for name, key in keys.items():
                self.assertIsInstance(key, PublicKey, name)
                self.assertFalse(hasattr(key, "sign"), name)
            self.assertFalse(hasattr(sim.policy, "agent_key"))
            self.assertFalse(hasattr(sim.policy, "merchant_keys"))
        finally:
            sim.close()
            os.path.exists(db) and os.remove(db)


class TestAuthenticationIsNotAuthorisation(unittest.TestCase):
    """A did:key resolves for anybody. That is the gap a credential closes."""

    def test_a_stranger_resolves_but_is_not_registered(self):
        stranger = Signer("stranger")
        resolver = Resolver()
        # we can tell whose signature it is...
        self.assertIsNotNone(resolver.resolve(stranger.did))
        # ...and still know we never onboarded them
        self.assertFalse(resolver.is_registered(stranger.did))
        self.assertNotIn(stranger.did, resolver)

    def test_a_gate_fails_closed_on_an_unregistered_signer(self):
        stranger = Signer("stranger")
        blob = b"pay me"
        self.assertFalse(
            Resolver().verify(stranger.did, blob, stranger.sign(blob))
        )


# --------------------------------------------------------------------------
# JWS
# --------------------------------------------------------------------------

class TestJws(unittest.TestCase):

    def setUp(self):
        self.owner = Signer("owner:ashutosh")
        self.token = jws_sign({"vct": REGISTRATION_VCT, "sub": "x"}, self.owner)

    def test_it_is_three_base64url_parts(self):
        self.assertEqual(len(self.token.split(".")), 3)

    def test_the_header_names_the_algorithm_and_the_key(self):
        header = json.loads(b64url_decode(self.token.split(".")[0]))
        self.assertEqual(header["alg"], "EdDSA")
        self.assertEqual(header["kid"], self.owner.did)

    def test_it_verifies_and_returns_the_signer(self):
        payload, kid = jws_verify(self.token)
        self.assertEqual(kid, self.owner.did)
        self.assertEqual(payload["vct"], REGISTRATION_VCT)

    def test_a_rewritten_payload_fails(self):
        head, _, sig = self.token.split(".")
        forged = jws_sign({"vct": REGISTRATION_VCT, "sub": "EVIL"}, Signer("x"))
        self.assertIsNone(jws_verify(f"{head}.{forged.split('.')[1]}.{sig}"))

    def test_rubbish_is_refused_rather_than_raising(self):
        for bad in ("", "abc", "a.b", "a.b.c", "...", "x.y.z.w"):
            self.assertIsNone(jws_verify(bad))

    def test_an_unregistered_issuer_is_refused_by_default(self):
        """The kid is a claim, not a permission."""
        resolver = Resolver()
        resolver.register("owner:ashutosh", self.owner)
        stranger_token = jws_sign({"vct": REGISTRATION_VCT}, Signer("stranger"))

        self.assertIsNotNone(jws_verify(self.token, resolver))
        self.assertIsNone(jws_verify(stranger_token, resolver))
        # ...but it can still be inspected, which is a different question
        self.assertIsNotNone(
            jws_verify(stranger_token, resolver, require_registered=False)
        )


# --------------------------------------------------------------------------
# Bitstring Status List
# --------------------------------------------------------------------------

class TestStatusList(unittest.TestCase):
    """Revocation lives here because did:key cannot express it."""

    def test_the_minimum_size_is_enforced(self):
        self.assertGreaterEqual(len(StatusList()), MIN_STATUS_BITS)
        with self.assertRaises(ValueError):
            StatusList(bits=64)

    def test_index_zero_is_the_leftmost_bit(self):
        """Stated explicitly by the spec, and easy to get backwards."""
        sl = StatusList()
        sl.set(0)
        raw = b64url_decode(sl.encoded()[1:])
        import gzip
        self.assertEqual(gzip.decompress(raw)[0] & 0b1000_0000, 0b1000_0000)

    def test_setting_one_bit_leaves_its_neighbours_alone(self):
        sl = StatusList()
        sl.set(9)
        self.assertTrue(sl.is_set(9))
        for other in (0, 8, 10, 4242):
            self.assertFalse(sl.is_set(other), other)

    def test_it_survives_the_wire_format(self):
        sl = StatusList()
        for i in (0, 5, 1000, MIN_STATUS_BITS - 1):
            sl.set(i)
        back = StatusList.from_encoded(sl.encoded())
        for i in (0, 5, 1000, MIN_STATUS_BITS - 1):
            self.assertTrue(back.is_set(i), i)
        self.assertFalse(back.is_set(6))

    def test_the_encoding_is_multibase_base64url(self):
        self.assertTrue(StatusList().encoded().startswith("u"))
        with self.assertRaises(ValueError):
            StatusList.from_encoded("zNotBase64url")

    def test_the_list_size_does_not_leak_how_many_agents_exist(self):
        """131,072 bits of mostly zeros gzip to the same tiny string."""
        empty, one = StatusList(), StatusList()
        one.set(77)
        self.assertLess(len(empty.encoded()), 200)
        self.assertLess(len(one.encoded()), 200)

    def test_out_of_range_indices_raise(self):
        sl = StatusList()
        for bad in (-1, MIN_STATUS_BITS, MIN_STATUS_BITS + 1):
            with self.assertRaises(IndexError):
                sl.is_set(bad)


# --------------------------------------------------------------------------
# The registration credential
# --------------------------------------------------------------------------

class RegistryCase(unittest.TestCase):

    def setUp(self):
        self.owner = Signer("owner:ashutosh")
        self.registry = AgentRegistry(self.owner, "ashutosh@okhdfc")
        self.coffee = Signer("agent:coffee")
        self.fuel = Signer("agent:fuel")


class TestRegistration(RegistryCase):

    def test_an_issued_registration_verifies(self):
        reg = self.registry.register_agent(self.coffee, "appliance-7")
        ok, reasons, claims = self.registry.verify(reg.token)
        self.assertTrue(ok, reasons)
        self.assertEqual(claims["agent_id"], "agent:coffee")
        self.assertEqual(claims["device_id"], "appliance-7")

    def test_the_credential_is_bound_to_the_agents_key(self):
        """RFC 7800: holding the credential is not enough, you need the key too."""
        reg = self.registry.register_agent(self.coffee, "appliance-7")
        _, _, claims = self.registry.verify(reg.token)
        self.assertEqual(claims["cnf"]["kid"], claims["sub"])
        self.assertEqual(claims["sub"], self.coffee.did)

    def test_the_owner_is_the_issuer_not_the_agent(self):
        """An agent vouching for itself proves nothing."""
        reg = self.registry.register_agent(self.coffee, "appliance-7")
        _, kid = jws_verify(reg.token)
        self.assertEqual(kid, self.owner.did)
        self.assertNotEqual(kid, self.coffee.did)

    def test_an_outsider_cannot_register_my_agent(self):
        imposter = AgentRegistry(Signer("imposter"), "imposter@okaxis")
        forged = imposter.register_agent(self.coffee, "appliance-7").token
        ok, reasons, _ = self.registry.verify(forged)
        self.assertFalse(ok)
        self.assertTrue(reasons)

    def test_an_expired_registration_is_refused(self):
        reg = self.registry.register_agent(
            self.coffee, "appliance-7", valid_for=timedelta(seconds=1)
        )
        ok, reasons, _ = self.registry.verify(
            reg.token, now=utcnow() + timedelta(days=2)
        )
        self.assertFalse(ok)
        self.assertIn("expired", " ".join(reasons))

    def test_registering_twice_is_refused(self):
        self.registry.register_agent(self.coffee, "appliance-7")
        with self.assertRaises(ValueError):
            self.registry.register_agent(self.coffee, "appliance-7")

    def test_the_attestation_admits_it_is_simulated(self):
        """A standard format does not make a stub real."""
        reg = self.registry.register_agent(self.coffee, "appliance-7")
        _, _, claims = self.registry.verify(reg.token)
        self.assertIs(claims["attestation"]["simulated"], True)
        self.assertEqual(claims["attestation"]["dbgstat"], "not-disabled")


class TestPerAgentRevocation(RegistryCase):
    """The brief asks for this by name: revoking one agent must not kill the rest."""

    def setUp(self):
        super().setUp()
        self.r_coffee = self.registry.register_agent(self.coffee, "appliance-7")
        self.r_fuel = self.registry.register_agent(self.fuel, "appliance-7")

    def test_both_agents_share_one_device(self):
        self.assertEqual(len(self.registry.agents_on_device("appliance-7")), 2)
        self.assertNotEqual(self.r_coffee.status_index, self.r_fuel.status_index)

    def test_revoking_one_leaves_the_other_running(self):
        self.registry.revoke_agent("agent:coffee")

        ok_coffee, reasons, _ = self.registry.verify(self.r_coffee.token)
        self.assertFalse(ok_coffee)
        self.assertIn("revoked", " ".join(reasons))

        ok_fuel, reasons_fuel, _ = self.registry.verify(self.r_fuel.token)
        self.assertTrue(ok_fuel, reasons_fuel)

    def test_revoking_an_unknown_agent_reports_failure(self):
        self.assertFalse(self.registry.revoke_agent("agent:nobody"))

    def test_revocation_survives_the_published_status_list(self):
        """A verifier fetching only the published list reaches the same verdict."""
        self.registry.revoke_agent("agent:coffee")
        published = self.registry.status_credential()

        fetched = StatusList.from_encoded(published["encodedList"])
        self.assertTrue(fetched.is_set(self.r_coffee.status_index))
        self.assertFalse(fetched.is_set(self.r_fuel.status_index))


# --------------------------------------------------------------------------
# The field the rail did not carry
# --------------------------------------------------------------------------

class TestAgentIdOnTheRail(unittest.TestCase):
    """Section II-C: 'the rail carries no field saying who or what started a debit'."""

    def setUp(self):
        self.db = tempfile.mktemp(suffix=".db")
        self.sim = simwiring.build(db_path=self.db, fresh=True)
        self.seeded = simwiring.seed(self.sim)
        self.umn = self.seeded["mandate"]["umn"]

    def tearDown(self):
        self.sim.close()
        if os.path.exists(self.db):
            os.remove(self.db)

    def _pay(self, agent_id=None, key="inv-1"):
        return self.sim.orchestrator.execute(
            intent=PaymentIntent(
                should_pay=True, payee_vpa=simwiring.MERCHANT_VPA,
                amount=Money.rupees("118"), reason="monthly invoice",
                confidence=0.95, source="rule",
            ),
            payer_vpa=simwiring.USER_VPA, idempotency_key=key,
            umn=self.umn, agent_id=agent_id,
        )

    def test_the_agent_rides_on_the_transaction(self):
        result = self._pay(agent_id=self.sim.agent_name)
        self.assertTrue(result.ok)
        self.assertEqual(result.txn.agent_id, self.sim.agent_name)

    def test_it_survives_a_round_trip_through_sqlite(self):
        result = self._pay(agent_id=self.sim.agent_name)
        stored = self.sim.store.get_txn(result.txn.txn_id)
        self.assertEqual(stored.agent_id, self.sim.agent_name)
        self.assertEqual(stored.to_dict()["agent_id"], self.sim.agent_name)

    def test_upi_today_leaves_it_empty(self):
        """Omitting it is the current behaviour, not an error."""
        result = self._pay(agent_id=None, key="inv-2")
        self.assertTrue(result.ok)
        self.assertIsNone(result.txn.agent_id)

    def test_the_authority_names_the_agent_it_was_granted_to(self):
        mandate = self.sim.store.get_mandate(self.umn)
        self.assertEqual(mandate.agent_id, self.sim.agent_name)

    def test_the_seeded_agent_is_registered_and_stored(self):
        stored = self.sim.store.get_registration(self.sim.agent_name)
        self.assertIsNotNone(stored)
        self.assertEqual(stored["device_id"], simwiring.DEVICE_ID)

        ok, reasons, _ = self.sim.registry.verify(stored["token"])
        self.assertTrue(ok, reasons)


if __name__ == "__main__":
    unittest.main(verbosity=2)
