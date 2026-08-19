"""Money, identifiers, and response codes.

Money is integer paise everywhere. Floats never touch an amount: 0.1 + 0.2 is
not 0.3, and a rounding error in a ledger is a defect you find months later
during reconciliation, not at the call site that caused it.
"""

from __future__ import annotations

import re
import secrets
import string
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# --------------------------------------------------------------------------
# Money
# --------------------------------------------------------------------------


@dataclass(frozen=True, order=True)
class Money:
    """An amount in integer paise. 1 rupee = 100 paise."""

    paise: int

    def __post_init__(self):
        if not isinstance(self.paise, int) or isinstance(self.paise, bool):
            raise TypeError(f"Money takes an int number of paise, got {self.paise!r}")

    # -- construction ------------------------------------------------------

    @classmethod
    def rupees(cls, value) -> "Money":
        """Money.rupees('1234.50') / Money.rupees(1234) -> Money(123450).

        Accepts str, int, or Decimal. Rejects float outright -- if a float got
        this far something upstream is already lossy.
        """
        if isinstance(value, float):
            raise TypeError(
                "refusing to build Money from a float; pass a str or Decimal"
            )
        try:
            dec = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"not a valid amount: {value!r}") from exc
        scaled = dec * 100
        if scaled != scaled.to_integral_value():
            raise ValueError(f"amount {value!r} is finer than one paisa")
        return cls(int(scaled))

    @classmethod
    def zero(cls) -> "Money":
        return cls(0)

    # -- arithmetic --------------------------------------------------------

    def __add__(self, other: "Money") -> "Money":
        return Money(self.paise + other.paise)

    def __sub__(self, other: "Money") -> "Money":
        return Money(self.paise - other.paise)

    def __neg__(self) -> "Money":
        return Money(-self.paise)

    @property
    def is_positive(self) -> bool:
        return self.paise > 0

    # -- rendering ---------------------------------------------------------

    def __str__(self) -> str:
        sign = "-" if self.paise < 0 else ""
        whole, frac = divmod(abs(self.paise), 100)
        return f"{sign}₹{whole:,}.{frac:02d}"

    def __repr__(self) -> str:
        return f"Money({self.paise})"

    def to_rupees_str(self) -> str:
        """Plain decimal string, no symbol -- for JSON payloads."""
        sign = "-" if self.paise < 0 else ""
        whole, frac = divmod(abs(self.paise), 100)
        return f"{sign}{whole}.{frac:02d}"


# --------------------------------------------------------------------------
# Identifiers
# --------------------------------------------------------------------------

_VPA_RE = re.compile(r"^[a-zA-Z0-9._-]{2,60}@[a-zA-Z][a-zA-Z0-9]{1,29}$")
_DIGITS = string.digits
_ALNUM = string.ascii_uppercase + string.digits


def validate_vpa(vpa: str) -> str:
    """A UPI Virtual Payment Address, e.g. 'ashutosh@okhdfc'."""
    if not _VPA_RE.match(vpa or ""):
        raise ValueError(f"malformed VPA: {vpa!r}")
    return vpa.lower()


def vpa_handle(vpa: str) -> str:
    """'ashutosh@okhdfc' -> 'okhdfc'. The switch routes on this."""
    return validate_vpa(vpa).split("@", 1)[1]


def new_rrn() -> str:
    """Retrieval Reference Number -- 12 digits, unique per transaction."""
    return "".join(secrets.choice(_DIGITS) for _ in range(12))


def new_upi_txn_id() -> str:
    """UPI transaction id -- 35 alphanumeric characters."""
    return "".join(secrets.choice(_ALNUM) for _ in range(35))


def new_umn() -> str:
    """Unique Mandate Number, as issued for a UPI AutoPay mandate."""
    body = "".join(secrets.choice(_ALNUM) for _ in range(20))
    return f"{body}@upisim"


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


# --------------------------------------------------------------------------
# Response codes
#
# The 2-character codes mirror the NPCI set closely enough to be recognisable.
# Codes prefixed SIM- are this simulator's own (mandate/policy rejections),
# marked so nobody mistakes them for real switch responses.
# --------------------------------------------------------------------------

SUCCESS = "00"

RESPONSE_CODES = {
    "00": "Approved / completed successfully",
    "Z9": "Insufficient funds in payer account",
    "U30": "Debit failed at remitter bank",
    "U31": "Credit failed at beneficiary bank",
    "BT": "Transaction timed out at the bank",
    "U28": "Beneficiary bank unavailable",
    "XH": "Account does not exist",
    "ZM": "Invalid MPIN / credential failure",
    "U16": "Risk threshold exceeded",
    "SIM-MANDATE": "Mandate validation failed (simulator)",
    "SIM-POLICY": "Blocked by agent policy engine (simulator)",
    "SIM-AGENT": "Agent declined to raise a payment (simulator)",
}


def describe(code: str) -> str:
    return RESPONSE_CODES.get(code, f"Unknown response code {code}")


class UpiError(Exception):
    """A rail-level failure carrying a UPI response code."""

    def __init__(self, code: str, message: str | None = None):
        self.code = code
        self.message = message or describe(code)
        super().__init__(f"[{code}] {self.message}")
