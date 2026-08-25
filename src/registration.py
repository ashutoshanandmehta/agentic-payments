"""
Agent registration: linking an agent to the human answerable for it.

Section II-C of the brief names the hole this fills. Authentication happens once,
when the mandate is created or the device is linked. Every debit after that is
unauthenticated by the human, and **the rail carries no field saying who or what
started it**. Until now this simulator reproduced that hole faithfully:
`Transaction` had no agent on it at all.

A registration is the missing field. It is a credential, issued by the owner,
saying: this agent, on this device, acts for me.

## Why a credential and not a database row

`identity.py` gives every agent a `did:key`, and a `did:key` proves authorship
perfectly -- the key is inside the identifier, so anyone can confirm a signature
without asking permission. What it cannot do is say the agent was *allowed* to
sign. An identifier authenticates. Only an issued credential authorises.

So the owner issues one, and it is a signed artifact rather than a row, because a
row is only evidence to whoever owns the database. In a dispute, the operator's
log against the merchant's log is not evidence. A credential the owner signed is.

## Why revocation lives somewhere else

`did:key` is generative. There is no registry entry to update and no deactivation
operation, so an identifier is valid for exactly as long as the key exists. You
therefore cannot revoke an agent by revoking its DID -- there is nothing to revoke.

Status goes in a separate list, and the credential points at it. That is
**Bitstring Status List v1.0**, a W3C Recommendation of 15 May 2025: one bit per
credential, gzipped, base64url-encoded, minimum 131,072 bits so the size of the
list never tells an observer how many agents you have.

Revoking agent 3 flips bit 3. Agents 1, 2 and 4 on the same device are untouched,
which is exactly the per-agent revocation the brief asks for.

## What the attestation claim is, and is not

The brief wants the agent's keys in trusted hardware. The claim here is shaped as
an **Entity Attestation Token** (RFC 9711, Proposed Standard, April 2025), with the
roles from the **RATS architecture** (RFC 9334, Informational, January 2023).

The shape is real. **The evidence is fabricated.** There is no TDX, no SEV-SNP and
no Secure Enclave quote behind it, because this runs on a laptop. A standard format
does not make a stub true, so every attestation carries `simulated: true` and
`dbgstat: "not-disabled"`, and `verify` will not let you forget it.

## Sources

- did:key v0.9 (W3C CCG draft)   https://w3c-ccg.github.io/did-key-spec/
- Bitstring Status List v1.0     https://www.w3.org/TR/vc-bitstring-status-list/
- RFC 7800, `cnf` claim          https://datatracker.ietf.org/doc/rfc7800/
- RFC 9711, EAT                  https://datatracker.ietf.org/doc/rfc9711/
- RFC 9334, RATS architecture    https://datatracker.ietf.org/doc/rfc9334/
- RFC 8037, EdDSA in JOSE        https://datatracker.ietf.org/doc/rfc8037/
"""

from __future__ import annotations

import gzip
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from core import new_id, validate_vpa
from identity import (
    Resolver,
    Signer,
    b64url,
    b64url_decode,
    jws_sign,
    jws_verify,
)
from models import iso, utcnow

#: schema version, following AP2's `mandate.checkout.open.1` convention
REGISTRATION_VCT = "agent.registration.1"

#: Bitstring Status List v1.0 requires at least this many bits, so that the
#: length of the list reveals nothing about how many credentials were issued.
MIN_STATUS_BITS = 131_072


# --------------------------------------------------------------------------
# Status list
# --------------------------------------------------------------------------

class StatusList:
    """One bit per agent. Set means revoked.

    Per the spec: index zero is the **left-most** bit of the first byte, the
    bitstring is GZIP compressed, and the result is multibase base64url -- the
    leading 'u' is the multibase tag for base64url, not part of the data.
    """

    def __init__(self, bits: int = MIN_STATUS_BITS, purpose: str = "revocation"):
        if bits < MIN_STATUS_BITS:
            raise ValueError(
                f"Bitstring Status List requires at least {MIN_STATUS_BITS} bits, "
                f"got {bits}"
            )
        self.purpose = purpose
        self._bits = bits
        self._bytes = bytearray(bits // 8)

    def __len__(self) -> int:
        return self._bits

    def _locate(self, index: int) -> tuple[int, int]:
        if not 0 <= index < self._bits:
            raise IndexError(f"status index {index} outside 0..{self._bits - 1}")
        # index 0 is the most significant bit of byte 0
        return index // 8, 7 - (index % 8)

    def set(self, index: int, revoked: bool = True) -> None:
        byte, bit = self._locate(index)
        if revoked:
            self._bytes[byte] |= 1 << bit
        else:
            self._bytes[byte] &= ~(1 << bit) & 0xFF

    def is_set(self, index: int) -> bool:
        byte, bit = self._locate(index)
        return bool(self._bytes[byte] >> bit & 1)

    # -- the wire format ---------------------------------------------------

    def encoded(self) -> str:
        """`encodedList`: gzip, then multibase base64url."""
        return "u" + b64url(gzip.compress(bytes(self._bytes)))

    @classmethod
    def from_encoded(cls, encoded: str, purpose: str = "revocation") -> "StatusList":
        if not encoded.startswith("u"):
            raise ValueError(
                f"expected multibase 'u' (base64url), got {encoded[:1]!r}"
            )
        raw = gzip.decompress(b64url_decode(encoded[1:]))
        out = cls(bits=max(len(raw) * 8, MIN_STATUS_BITS), purpose=purpose)
        out._bytes[: len(raw)] = raw
        return out

    def to_credential(self, issuer_did: str, list_id: str) -> dict[str, Any]:
        return {
            "vct": "status.bitstring.1",
            "id": list_id,
            "iss": issuer_did,
            "statusPurpose": self.purpose,
            "encodedList": self.encoded(),
        }


# --------------------------------------------------------------------------
# The registration credential
# --------------------------------------------------------------------------

@dataclass
class AgentRegistration:
    """What the owner signed about one agent."""

    agent_id: str
    agent_did: str
    owner_vpa: str
    owner_did: str
    device_id: str
    status_index: int
    token: str = ""
    issued_at: Any = field(default_factory=utcnow)
    expires_at: Any = None

    @property
    def id(self) -> str:
        return self.agent_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_did": self.agent_did,
            "owner_vpa": self.owner_vpa,
            "owner_did": self.owner_did,
            "device_id": self.device_id,
            "status_index": self.status_index,
            "issued_at": iso(self.issued_at),
            "expires_at": iso(self.expires_at),
            "token": self.token,
        }


def _attestation(device_id: str) -> dict[str, Any]:
    """An EAT-shaped claim set. The shape is real; the evidence is not.

    `ueid` is the Universal Entity ID -- the device. `dbgstat` reports whether
    debug is disabled, and on a laptop it plainly is not. `simulated` exists so
    nothing downstream can quietly treat this as a hardware root of trust.
    """
    return {
        "ueid": device_id,
        "eat_profile": "urn:sim:agentic-payments:laptop",
        "dbgstat": "not-disabled",
        "oemid": "SIM",
        "simulated": True,
    }


# --------------------------------------------------------------------------
# The registry
# --------------------------------------------------------------------------

class AgentRegistry:
    """Issues registrations, and answers whether one still stands.

    Holds the status list, because status is the part `did:key` cannot express.
    """

    def __init__(self, owner_key: Signer, owner_vpa: str,
                 resolver: Resolver | None = None,
                 list_id: str = "urn:sim:status:agents"):
        self.owner_key = owner_key
        self.owner_vpa = validate_vpa(owner_vpa)
        self.resolver = resolver or Resolver()
        self.status = StatusList()
        self.list_id = list_id
        self._by_id: dict[str, AgentRegistration] = {}
        self._next_index = 0
        self.resolver.register(owner_key.label, owner_key)

    # -- issuing -----------------------------------------------------------

    def register_agent(
        self,
        agent_key: Signer,
        device_id: str,
        agent_id: str | None = None,
        valid_for: timedelta = timedelta(days=365),
    ) -> AgentRegistration:
        """Issue a registration credential for one agent on one device."""
        agent_id = agent_id or agent_key.label or new_id("agent")
        if agent_id in self._by_id:
            raise ValueError(f"{agent_id} is already registered")

        now = utcnow()
        expires = now + valid_for
        index = self._next_index
        self._next_index += 1

        claims = {
            "vct": REGISTRATION_VCT,
            "iss": self.owner_key.did,
            "sub": agent_key.did,
            # RFC 7800: the credential is bound to the key the agent will sign with,
            # so presenting it is not enough -- you must hold that key too.
            "cnf": {"kid": agent_key.did},
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
            "agent_id": agent_id,
            "owner_vpa": self.owner_vpa,
            "device_id": device_id,
            "attestation": _attestation(device_id),
            "credentialStatus": {
                "type": "BitstringStatusListEntry",
                "statusPurpose": self.status.purpose,
                "statusListIndex": str(index),
                "statusListCredential": self.list_id,
            },
        }

        reg = AgentRegistration(
            agent_id=agent_id,
            agent_did=agent_key.did,
            owner_vpa=self.owner_vpa,
            owner_did=self.owner_key.did,
            device_id=device_id,
            status_index=index,
            token=jws_sign(claims, self.owner_key),
            issued_at=now,
            expires_at=expires,
        )

        self._by_id[agent_id] = reg
        self.resolver.register(agent_id, agent_key)
        return reg

    # -- revoking ----------------------------------------------------------

    def revoke_agent(self, agent_id: str) -> bool:
        """Flip this agent's bit. Every other agent's bit is untouched.

        That isolation is the point: two agents on one appliance are two
        credentials at two indices, so switching one off cannot switch off the
        other. Revoking the *device* would.
        """
        reg = self._by_id.get(agent_id)
        if reg is None:
            return False
        self.status.set(reg.status_index, True)
        return True

    def is_revoked(self, agent_id: str) -> bool:
        reg = self._by_id.get(agent_id)
        return reg is not None and self.status.is_set(reg.status_index)

    # -- checking ----------------------------------------------------------

    def verify(self, token: str, now=None) -> tuple[bool, list[str], dict]:
        """Is this registration good right now?

        Returns `(ok, reasons, claims)`. Verification runs entirely off public
        keys -- this is the check a switch would run, holding nothing secret.
        """
        reasons: list[str] = []
        now = now or utcnow()

        out = jws_verify(token, self.resolver)
        if out is None:
            return False, ["the registration does not verify against any known issuer"], {}
        claims, kid = out

        if claims.get("vct") != REGISTRATION_VCT:
            reasons.append(
                f"wrong credential type {claims.get('vct')!r}, "
                f"expected {REGISTRATION_VCT!r}"
            )

        # The signature says who signed. It does not say they were entitled to.
        # The owner is the only party who can vouch for their own agent.
        if kid != self.owner_key.did:
            reasons.append("the registration was not issued by this owner")

        # RFC 7800: subject and confirmation key must agree, or the credential
        # describes one agent while authorising another.
        if claims.get("cnf", {}).get("kid") != claims.get("sub"):
            reasons.append("the confirmation key does not match the subject")

        exp = claims.get("exp")
        if exp is not None and now.timestamp() > exp:
            reasons.append("the registration has expired")

        agent_id = claims.get("agent_id", "")
        if self.is_revoked(agent_id):
            reasons.append(f"{agent_id} is revoked in the status list")

        return not reasons, reasons, claims

    # -- lookups -----------------------------------------------------------

    def get(self, agent_id: str) -> AgentRegistration | None:
        return self._by_id.get(agent_id)

    def agents_on_device(self, device_id: str) -> list[AgentRegistration]:
        return [r for r in self._by_id.values() if r.device_id == device_id]

    def status_credential(self) -> dict[str, Any]:
        return self.status.to_credential(self.owner_key.did, self.list_id)

    def __len__(self) -> int:
        return len(self._by_id)
