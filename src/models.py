"""Domain objects and the transaction state machine."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone

from core import Money


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


# --------------------------------------------------------------------------
# Transaction lifecycle
# --------------------------------------------------------------------------


class TxnState(str, enum.Enum):
    CREATED = "CREATED"
    AUTHORIZED = "AUTHORIZED"          # mandate + policy passed
    DEBIT_PENDING = "DEBIT_PENDING"
    DEBITED = "DEBITED"
    CREDIT_PENDING = "CREDIT_PENDING"
    CREDITED = "CREDITED"
    SETTLED = "SETTLED"                # terminal, success

    DECLINED = "DECLINED"              # terminal, never touched money
    TIMED_OUT = "TIMED_OUT"            # debited, credit outcome unknown
    REVERSED = "REVERSED"              # terminal, money returned
    FAILED = "FAILED"                  # terminal, gave up

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL

    @property
    def is_success(self) -> bool:
        return self is TxnState.SETTLED


_TERMINAL = {
    TxnState.SETTLED,
    TxnState.DECLINED,
    TxnState.REVERSED,
    TxnState.FAILED,
}

# Only these moves are legal. Anything else is a bug, and the store raises
# rather than silently writing an impossible state.
ALLOWED_TRANSITIONS: dict[TxnState, set[TxnState]] = {
    TxnState.CREATED: {TxnState.AUTHORIZED, TxnState.DECLINED},
    TxnState.AUTHORIZED: {TxnState.DEBIT_PENDING, TxnState.DECLINED},
    TxnState.DEBIT_PENDING: {TxnState.DEBITED, TxnState.DECLINED, TxnState.TIMED_OUT},
    TxnState.DEBITED: {TxnState.CREDIT_PENDING, TxnState.REVERSED, TxnState.TIMED_OUT},
    TxnState.CREDIT_PENDING: {TxnState.CREDITED, TxnState.TIMED_OUT, TxnState.REVERSED},
    TxnState.CREDITED: {TxnState.SETTLED},
    TxnState.TIMED_OUT: {TxnState.CREDITED, TxnState.REVERSED, TxnState.FAILED},
    TxnState.SETTLED: set(),
    TxnState.DECLINED: set(),
    TxnState.REVERSED: set(),
    TxnState.FAILED: set(),
}


def can_transition(src: TxnState, dst: TxnState) -> bool:
    return dst in ALLOWED_TRANSITIONS[src]


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------


class AccountType(str, enum.Enum):
    USER = "USER"                # payer, holds a UPI-linked balance
    MERCHANT = "MERCHANT"        # beneficiary
    SUSPENSE = "SUSPENSE"        # in-flight funds between debit and credit
    AGENT_CARD = "AGENT_CARD"    # an agent's virtual card: money it controls directly


@dataclass
class Account:
    account_id: str
    vpa: str
    holder_name: str
    bank_handle: str
    account_type: AccountType
    balance: Money

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "vpa": self.vpa,
            "holder_name": self.holder_name,
            "bank_handle": self.bank_handle,
            "type": self.account_type.value,
            "balance": self.balance.to_rupees_str(),
            "balance_paise": self.balance.paise,
        }


# --------------------------------------------------------------------------
# Mandates -- the agent's spending authority
# --------------------------------------------------------------------------


class MandateStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    REVOKED = "REVOKED"
    EXHAUSTED = "EXHAUSTED"


@dataclass
class Mandate:
    """A scoped, revocable pre-authorisation, modelled on UPI AutoPay.

    This is the whole security story for an autonomous payer: the agent never
    holds open-ended authority to move money, only whatever a mandate grants.
    """

    umn: str
    payer_vpa: str
    allowed_payees: list[str]        # explicit VPAs; ["*"] means any
    max_amount_per_txn: Money
    total_cap: Money
    consumed: Money
    valid_from: datetime
    valid_until: datetime
    status: MandateStatus
    purpose: str
    created_at: datetime = field(default_factory=utcnow)

    @property
    def remaining(self) -> Money:
        return self.total_cap - self.consumed

    def to_dict(self) -> dict:
        return {
            "umn": self.umn,
            "payer_vpa": self.payer_vpa,
            "allowed_payees": self.allowed_payees,
            "max_amount_per_txn": self.max_amount_per_txn.to_rupees_str(),
            "total_cap": self.total_cap.to_rupees_str(),
            "consumed": self.consumed.to_rupees_str(),
            "remaining": self.remaining.to_rupees_str(),
            "valid_from": iso(self.valid_from),
            "valid_until": iso(self.valid_until),
            "status": self.status.value,
            "purpose": self.purpose,
            "created_at": iso(self.created_at),
        }


# --------------------------------------------------------------------------
# Transactions
# --------------------------------------------------------------------------


@dataclass
class Transaction:
    txn_id: str
    upi_txn_id: str
    rrn: str
    idempotency_key: str
    payer_vpa: str
    payee_vpa: str
    amount: Money
    state: TxnState
    response_code: str | None
    umn: str | None
    note: str
    attempts: int = 0
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        return {
            "txn_id": self.txn_id,
            "upi_txn_id": self.upi_txn_id,
            "rrn": self.rrn,
            "idempotency_key": self.idempotency_key,
            "payer_vpa": self.payer_vpa,
            "payee_vpa": self.payee_vpa,
            "amount": self.amount.to_rupees_str(),
            "amount_paise": self.amount.paise,
            "state": self.state.value,
            "response_code": self.response_code,
            "umn": self.umn,
            "note": self.note,
            "attempts": self.attempts,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }


# --------------------------------------------------------------------------
# Ledger
# --------------------------------------------------------------------------


class Direction(str, enum.Enum):
    DEBIT = "DR"
    CREDIT = "CR"


@dataclass
class LedgerEntry:
    entry_id: str
    txn_id: str
    account_id: str
    direction: Direction
    amount: Money
    narrative: str
    created_at: datetime = field(default_factory=utcnow)

    @property
    def signed_paise(self) -> int:
        """Credits are positive, debits negative. A balanced set sums to zero."""
        return self.amount.paise if self.direction is Direction.CREDIT else -self.amount.paise

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "txn_id": self.txn_id,
            "account_id": self.account_id,
            "direction": self.direction.value,
            "amount": self.amount.to_rupees_str(),
            "narrative": self.narrative,
            "created_at": iso(self.created_at),
        }


# --------------------------------------------------------------------------
# Agent intent -- what the model produces, before any gate runs
# --------------------------------------------------------------------------


@dataclass
class PaymentIntent:
    should_pay: bool
    payee_vpa: str | None
    amount: Money | None
    reason: str
    confidence: float
    source: str = "llm"          # "llm" or "rule" (deterministic fallback)

    def to_dict(self) -> dict:
        return {
            "should_pay": self.should_pay,
            "payee_vpa": self.payee_vpa,
            "amount": self.amount.to_rupees_str() if self.amount else None,
            "reason": self.reason,
            "confidence": self.confidence,
            "source": self.source,
        }
