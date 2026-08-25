"""
Who signed a thing, and how somebody else checks it without holding the secret.

The order gate got away without this. It only ever asked *what does a signature
prove*, and for that question it does not matter that `consent.Keypair` verifies by
reaching for its own private key -- there was nobody to fool.

Registration and receipts cannot get away with it. Their whole claim is that a
verifier who holds **no private key** can check the evidence. If verification needs
the secret, the evidence proves nothing to anyone except the party that wrote it,
which is the opposite of what a receipt is for.

So this module splits the two halves apart:

    Signer      holds a private key. Can sign. Nobody else has it.
    PublicKey   holds only the public half. Can verify, and nothing else.
    Resolver    turns an identifier back into a PublicKey.

## Identifiers are `did:key`

A DID is a Decentralised Identifier -- a string that names a subject without a
central registry issuing it. The `did:key` method is the simplest one that exists:
the identifier *is* the public key, encoded. Nothing is stored anywhere, nothing is
looked up over a network, and resolving it is pure arithmetic on the string itself.

    did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP
            ^^                                                multibase: base58-btc
              ^^^^                                            multicodec: Ed25519

That property is why it fits here. A laptop simulation with no network and no
registry can still do real public-key verification, and a reviewer can re-derive
every identifier from the key bytes by hand.

**It also cannot be revoked.** `did:key` is generative -- there is no registry entry
to update or deactivate, so an identifier is valid for as long as the key exists.
Revocation therefore cannot live here. It lives in a separate status credential,
which is `registration.py`'s problem, not this file's.

Source: The did:key Method v0.9, W3C Credentials Community Group.
https://w3c-ccg.github.io/did-key-spec/
Note it is a Community Group draft, **not** a W3C Recommendation.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from hashlib import sha256

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )
    CRYPTO = True
except ImportError:                                        # pragma: no cover
    CRYPTO = False


# --------------------------------------------------------------------------
# base58-btc
#
# Bitcoin's alphabet: the ten digits and both cases, minus the four characters
# that are easy to misread out loud or in a screenshot -- 0, O, I and l. That is
# the only reason this encoding exists rather than base64.
# --------------------------------------------------------------------------

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_INDEX = {c: i for i, c in enumerate(_B58)}


def b58encode(raw: bytes) -> str:
    """Bytes -> base58-btc. Leading zero bytes become leading '1's."""
    leading_zeros = len(raw) - len(raw.lstrip(b"\x00"))

    n = int.from_bytes(raw, "big")
    out = ""
    while n > 0:
        n, rem = divmod(n, 58)
        out = _B58[rem] + out

    return "1" * leading_zeros + out


def b58decode(text: str) -> bytes:
    """base58-btc -> bytes. Raises on any character outside the alphabet."""
    leading_ones = len(text) - len(text.lstrip("1"))

    n = 0
    for ch in text:
        if ch not in _B58_INDEX:
            raise ValueError(f"{ch!r} is not a base58-btc character")
        n = n * 58 + _B58_INDEX[ch]

    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\x00" * leading_ones + body


# --------------------------------------------------------------------------
# did:key
#
# The multicodec prefix for an Ed25519 public key is 0xed. Multicodec numbers are
# varint-encoded, and 0xed needs two bytes as a varint -- 0xed 0x01 -- which is why
# every Ed25519 did:key starts with the same "z6Mk" once it is base58'd.
# --------------------------------------------------------------------------

ED25519_MULTICODEC = b"\xed\x01"
DID_KEY_PREFIX = "did:key:"


def encode_did_key(public_bytes: bytes) -> str:
    """32 raw Ed25519 public key bytes -> a did:key identifier."""
    if len(public_bytes) != 32:
        raise ValueError(
            f"an Ed25519 public key is 32 bytes, got {len(public_bytes)}"
        )
    return DID_KEY_PREFIX + "z" + b58encode(ED25519_MULTICODEC + public_bytes)


def decode_did_key(did: str) -> bytes:
    """A did:key identifier -> 32 raw Ed25519 public key bytes.

    This is the whole of `did:key` resolution. There is no network call and no
    registry, which is exactly why the method cannot express revocation.
    """
    if not did.startswith(DID_KEY_PREFIX):
        raise ValueError(f"not a did:key: {did!r}")

    body = did[len(DID_KEY_PREFIX):]
    if not body.startswith("z"):
        raise ValueError(
            f"expected multibase 'z' (base58-btc), got {body[:1]!r} in {did!r}"
        )

    raw = b58decode(body[1:])
    if not raw.startswith(ED25519_MULTICODEC):
        raise ValueError(
            f"{did!r} is not an Ed25519 key (multicodec {raw[:2].hex()}, "
            f"expected {ED25519_MULTICODEC.hex()})"
        )

    public_bytes = raw[len(ED25519_MULTICODEC):]
    if len(public_bytes) != 32:
        raise ValueError(
            f"{did!r} decodes to {len(public_bytes)} bytes, expected 32"
        )
    return public_bytes


# --------------------------------------------------------------------------
# The two halves
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class PublicKey:
    """The half you can hand to anyone. Verifies, and cannot sign.

    There is deliberately no `sign` method and no route back to a private key. A
    verifier that ends up holding one has stopped being a verifier.
    """

    raw: bytes
    label: str = ""

    def __post_init__(self):
        if len(self.raw) != 32:
            raise ValueError(
                f"an Ed25519 public key is 32 bytes, got {len(self.raw)}"
            )

    @property
    def did(self) -> str:
        return encode_did_key(self.raw)

    def verify(self, blob: bytes, signature: bytes) -> bool:
        if not signature:
            return False
        if not CRYPTO:                                     # pragma: no cover
            return signature == _stub_signature(self.label, blob)
        try:
            Ed25519PublicKey.from_public_bytes(self.raw).verify(signature, blob)
            return True
        except InvalidSignature:
            return False

    @classmethod
    def from_did(cls, did: str, label: str = "") -> "PublicKey":
        return cls(raw=decode_did_key(did), label=label or did)

    def __repr__(self) -> str:
        return f"PublicKey({self.label or self.did})"


class Signer:
    """The half that stays put. Signs, and hands out its public half on request."""

    def __init__(self, label: str, private_bytes: bytes | None = None) -> None:
        self.label = label
        if not CRYPTO:                                     # pragma: no cover
            self._private = None
            self._public_bytes = sha256(label.encode()).digest()
            return

        self._private = (
            Ed25519PrivateKey.from_private_bytes(private_bytes)
            if private_bytes is not None
            else Ed25519PrivateKey.generate()
        )
        self._public_bytes = self._private.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )

    # -- the public half ---------------------------------------------------

    @property
    def public(self) -> PublicKey:
        return PublicKey(raw=self._public_bytes, label=self.label)

    @property
    def did(self) -> str:
        return self.public.did

    # -- signing -----------------------------------------------------------

    def sign(self, blob: bytes) -> bytes:
        if not CRYPTO:                                     # pragma: no cover
            return _stub_signature(self.label, blob)
        return self._private.sign(blob)

    def verify(self, blob: bytes, signature: bytes) -> bool:
        """Kept so existing callers keep working. Prefer `.public.verify`.

        A signer verifying its own signature proves nothing to a third party. It
        is here for compatibility with `consent.Keypair`, not because it is a
        sensible thing to do.
        """
        return self.public.verify(blob, signature)

    # -- persistence -------------------------------------------------------

    def private_bytes(self) -> bytes:
        """Seed bytes, so a test can rebuild the same signer deterministically."""
        if not CRYPTO:                                     # pragma: no cover
            raise RuntimeError("no private key material without `cryptography`")
        return self._private.private_bytes(
            Encoding.Raw, PrivateFormat.Raw, NoEncryption()
        )

    def __repr__(self) -> str:
        return f"Signer({self.label})"


def _stub_signature(label: str, blob: bytes) -> bytes:
    """Fallback when `cryptography` is absent. Proves nothing; keeps tests running."""
    return sha256(label.encode() + blob).digest()


# --------------------------------------------------------------------------
# Resolving an identifier back to a key
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# JWS, compact serialisation
#
# The rest of this codebase signs canonical JSON and keeps the signature beside
# it. That is fine internally and useless to anybody else, because the format is
# ours. A JWS is the same idea written the way every other system expects:
#
#     base64url(header) . base64url(payload) . base64url(signature)
#
# The header names the algorithm and the key, so a verifier who is handed nothing
# but the string can work out what to check and against what. That is what makes
# an artifact evidence rather than a log line.
#
# `alg: EdDSA` over Ed25519 is RFC 8037, "CFRG Elliptic Curve Diffie-Hellman
# (ECDH) and Signatures in JOSE", Proposed Standard, January 2017.
# https://datatracker.ietf.org/doc/rfc8037/
# --------------------------------------------------------------------------

def b64url(raw: bytes) -> str:
    """base64url, no padding, as JOSE requires."""
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def b64url_decode(text: str) -> bytes:
    """base64url with the padding put back before decoding."""
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def jws_sign(payload: dict, signer: Signer, typ: str = "JWT") -> str:
    """Sign a claim set and return a compact JWS.

    `kid` is the signer's `did:key`, so the token carries the means of checking
    itself: no registry lookup, no key distribution, no prior arrangement.
    """
    header = {"alg": "EdDSA", "typ": typ, "kid": signer.did}
    signing_input = (
        b64url(json.dumps(header, sort_keys=True, separators=(",", ":")).encode())
        + "."
        + b64url(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    )
    signature = signer.sign(signing_input.encode())
    return signing_input + "." + b64url(signature)


def jws_verify(
    token: str,
    resolver: Resolver | None = None,
    require_registered: bool = True,
) -> tuple[dict, str] | None:
    """Check a compact JWS. Returns `(payload, kid)`, or None if it does not verify.

    **The `kid` is a claim, not a permission.** Anyone can mint a token naming
    their own key, and it will verify perfectly -- it is genuinely their signature
    over their own claims. A valid signature establishes *who* signed and never
    whether that party was entitled to say it. The caller must still check the
    returned `kid` is the party it expected. Skipping that is the standard way JWT
    verification gets built wrong.

    With a `resolver` and `require_registered=True` (the default), a signer the
    resolver has never onboarded is refused even though its `did:key` would resolve
    perfectly well on its own. Pass `require_registered=False` to accept any
    self-describing key -- useful for inspecting an artifact, not for admitting one.
    """
    parts = token.split(".")
    if len(parts) != 3:
        return None
    header_b64, payload_b64, signature_b64 = parts

    try:
        header = json.loads(b64url_decode(header_b64))
        payload = json.loads(b64url_decode(payload_b64))
        signature = b64url_decode(signature_b64)
    except (ValueError, json.JSONDecodeError):
        return None

    if header.get("alg") != "EdDSA":
        return None

    kid = header.get("kid", "")
    if resolver is not None and require_registered and not resolver.is_registered(kid):
        return None

    key = resolver.resolve(kid) if resolver is not None else None
    if key is None:
        try:
            key = PublicKey.from_did(kid)
        except ValueError:
            return None

    signing_input = f"{header_b64}.{payload_b64}".encode()
    if not key.verify(signing_input, signature):
        return None
    return payload, kid


class Resolver:
    """Identifier -> PublicKey.

    Holds public keys only. This is the object the policy engine and the receipt
    verifier get, and the reason they can be pointed at evidence they did not
    produce and still reach a verdict.

    A `did:key` resolves with no registration at all, because the key is inside the
    identifier. Anything else -- a VPA like `brewhouse@ybl`, an agent label -- has
    to be registered first, the way a switch holds the public keys of the parties
    it has onboarded.
    """

    def __init__(self, keys: dict[str, PublicKey] | None = None) -> None:
        self._keys: dict[str, PublicKey] = dict(keys or {})

    def register(self, name: str, key: PublicKey | Signer) -> PublicKey:
        """Onboard a named party. Accepts a Signer and keeps only its public half."""
        public = key.public if isinstance(key, Signer) else key
        self._keys[name] = public
        # a party is always reachable by its did as well as by its name
        self._keys.setdefault(public.did, public)
        return public

    def is_registered(self, name: str) -> bool:
        """Was this party actually onboarded here?

        Deliberately **not** the same question as `resolve`. A `did:key` resolves
        for anybody, because the key is inside the identifier -- so resolving it
        tells you a signature is genuinely theirs, and nothing whatsoever about
        whether they were allowed to sign it.

        That gap is the whole reason a registration credential has to exist. An
        identifier authenticates. Only an issued credential authorises.
        """
        return name in self._keys

    def resolve(self, name: str) -> PublicKey | None:
        """Get a key to check a signature with.

        Registered name first, then `did:key` arithmetic for anyone else. Answers
        "whose signature is this", not "may they act". Use `is_registered` for that.
        """
        if name in self._keys:
            return self._keys[name]
        if name.startswith(DID_KEY_PREFIX):
            try:
                return PublicKey.from_did(name)
            except ValueError:
                return None
        return None

    def verify(self, name: str, blob: bytes, signature: bytes) -> bool:
        """Verify a signature by a party this resolver has onboarded.

        Registration is required, so an unknown signer fails closed even when its
        `did:key` would resolve on its own. A gate is the wrong place to be
        permissive: "I can tell whose signature this is" is not a reason to honour
        it. Use `resolve` directly when you want the looser question.
        """
        if not self.is_registered(name):
            return False
        return self._keys[name].verify(blob, signature)

    def known(self) -> list[str]:
        return sorted(self._keys)

    def __contains__(self, name: str) -> bool:
        """Membership means *registered*, the stricter of the two questions."""
        return self.is_registered(name)

    def __repr__(self) -> str:
        return f"Resolver({len(self._keys)} keys)"
