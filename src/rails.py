"""Simulated UPI rails: remitter bank, beneficiary bank, and the switch.

Topology mirrors the real thing closely enough for the failure modes to be the
interesting part:

    PSP (payer app)  ->  Switch (NPCI-like)  ->  Remitter bank   (debit)
                                             ->  Beneficiary bank (credit)

The switch routes on the VPA handle (`ashutosh@okhdfc` -> `okhdfc`), assigns
the RRN, and is the only component that talks to both banks. Money moves in
two legs with a suspense account in between, so a transaction that has been
debited but not yet credited is a real, visible state rather than an
accounting fiction -- which is what makes reversal and reconciliation
meaningful here.

Faults are injected deterministically (by rule) or probabilistically, so a
demo can reproduce a specific failure on demand.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from core import Money, UpiError, new_id, vpa_handle
from models import AccountType, Direction, LedgerEntry, Transaction
from store import SUSPENSE_ACCOUNT_ID, Store

# --------------------------------------------------------------------------
# Fault injection
# --------------------------------------------------------------------------

FAULTS = (
    "insufficient_funds",     # payer can't cover it -> Z9, clean decline
    "debit_fail",             # remitter bank rejects -> U30, clean decline
    "invalid_mpin",           # credential failure -> ZM, clean decline
    "debit_timeout",          # bank debited but the response was lost -> BT
    "credit_fail",            # credit rejected after a good debit -> U31
    "beneficiary_down",       # beneficiary bank offline -> U28
    "credit_timeout",         # credit outcome unknown -> BT, needs recon
)


@dataclass
class FaultConfig:
    """Which faults to inject, and how.

    `force` fires the named fault on the next matching leg and then clears
    itself -- that is what the CLI's `--fail` flag uses so a demo can show a
    specific failure on demand. `probabilities` drives soak testing.
    """

    force: str | None = None
    probabilities: dict[str, float] = field(default_factory=dict)
    seed: int | None = None
    _rng: random.Random = field(init=False, repr=False, default=None)

    def __post_init__(self):
        if self.force and self.force not in FAULTS:
            raise ValueError(f"unknown fault {self.force!r}; expected one of {FAULTS}")
        for name in self.probabilities:
            if name not in FAULTS:
                raise ValueError(f"unknown fault {name!r}; expected one of {FAULTS}")
        self._rng = random.Random(self.seed)

    def fires(self, fault: str) -> bool:
        if self.force == fault:
            self.force = None          # one-shot
            return True
        p = self.probabilities.get(fault, 0.0)
        return p > 0 and self._rng.random() < p

    def clear(self):
        self.force = None
        self.probabilities = {}


# --------------------------------------------------------------------------
# Banks
# --------------------------------------------------------------------------


class Bank:
    """One bank, addressed by its UPI handle (the part after the '@')."""

    def __init__(self, handle: str, store: Store, faults: FaultConfig):
        self.handle = handle
        self.store = store
        self.faults = faults

    # -- remitter side -----------------------------------------------------

    def debit(self, txn: Transaction) -> str:
        """Move funds from the payer to the suspense account.

        Returns a response code. `BT` is the nasty one: the debit *has*
        happened, but the caller never learns whether it did -- exactly the
        case reconciliation exists for.
        """
        payer = self.store.get_account_by_vpa(txn.payer_vpa)
        if payer is None:
            raise UpiError("XH", f"no account for {txn.payer_vpa}")

        if self.faults.fires("invalid_mpin"):
            raise UpiError("ZM")
        if self.faults.fires("debit_fail"):
            raise UpiError("U30")
        if self.faults.fires("insufficient_funds") or payer.balance < txn.amount:
            raise UpiError("Z9", f"balance {payer.balance} < {txn.amount}")

        self.store.post_entries([
            LedgerEntry(
                entry_id=new_id("led"), txn_id=txn.txn_id, account_id=payer.account_id,
                direction=Direction.DEBIT, amount=txn.amount,
                narrative=f"UPI debit to {txn.payee_vpa} (RRN {txn.rrn})",
            ),
            LedgerEntry(
                entry_id=new_id("led"), txn_id=txn.txn_id, account_id=SUSPENSE_ACCOUNT_ID,
                direction=Direction.CREDIT, amount=txn.amount,
                narrative=f"In flight from {txn.payer_vpa} (RRN {txn.rrn})",
            ),
        ])

        # Debit is committed. Losing the response now is what makes this hard.
        if self.faults.fires("debit_timeout"):
            raise UpiError("BT", "debit committed but response lost")
        return "00"

    def reverse_debit(self, txn: Transaction) -> str:
        """Return in-flight funds to the payer."""
        payer = self.store.get_account_by_vpa(txn.payer_vpa)
        if payer is None:
            raise UpiError("XH", f"no account for {txn.payer_vpa}")
        self.store.post_entries([
            LedgerEntry(
                entry_id=new_id("led"), txn_id=txn.txn_id, account_id=SUSPENSE_ACCOUNT_ID,
                direction=Direction.DEBIT, amount=txn.amount,
                narrative=f"Reversal out of suspense (RRN {txn.rrn})",
            ),
            LedgerEntry(
                entry_id=new_id("led"), txn_id=txn.txn_id, account_id=payer.account_id,
                direction=Direction.CREDIT, amount=txn.amount,
                narrative=f"UPI reversal for RRN {txn.rrn}",
            ),
        ])
        return "00"

    # -- beneficiary side --------------------------------------------------

    def credit(self, txn: Transaction) -> str:
        """Move in-flight funds from suspense to the merchant."""
        payee = self.store.get_account_by_vpa(txn.payee_vpa)
        if payee is None:
            raise UpiError("XH", f"no account for {txn.payee_vpa}")

        if self.faults.fires("beneficiary_down"):
            raise UpiError("U28")
        if self.faults.fires("credit_fail"):
            raise UpiError("U31")

        self.store.post_entries([
            LedgerEntry(
                entry_id=new_id("led"), txn_id=txn.txn_id, account_id=SUSPENSE_ACCOUNT_ID,
                direction=Direction.DEBIT, amount=txn.amount,
                narrative=f"Settlement to {txn.payee_vpa} (RRN {txn.rrn})",
            ),
            LedgerEntry(
                entry_id=new_id("led"), txn_id=txn.txn_id, account_id=payee.account_id,
                direction=Direction.CREDIT, amount=txn.amount,
                narrative=f"UPI credit from {txn.payer_vpa} (RRN {txn.rrn})",
            ),
        ])

        if self.faults.fires("credit_timeout"):
            raise UpiError("BT", "credit committed but response lost")
        return "00"

    def credit_posted(self, txn: Transaction) -> bool:
        """Did the credit leg actually land? The switch asks this during recon."""
        payee = self.store.get_account_by_vpa(txn.payee_vpa)
        if payee is None:
            return False
        return any(
            e.account_id == payee.account_id and e.direction is Direction.CREDIT
            for e in self.store.ledger_for_txn(txn.txn_id)
        )

    def debit_posted(self, txn: Transaction) -> bool:
        payer = self.store.get_account_by_vpa(txn.payer_vpa)
        if payer is None:
            return False
        return any(
            e.account_id == payer.account_id and e.direction is Direction.DEBIT
            for e in self.store.ledger_for_txn(txn.txn_id)
        )


# --------------------------------------------------------------------------
# Switch
# --------------------------------------------------------------------------


@dataclass
class RailResponse:
    code: str
    message: str
    leg: str

    @property
    def ok(self) -> bool:
        return self.code == "00"

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "leg": self.leg, "ok": self.ok}


class Switch:
    """NPCI-like switch. Routes by VPA handle and owns both legs."""

    def __init__(self, store: Store, faults: FaultConfig | None = None):
        self.store = store
        self.faults = faults or FaultConfig()
        self._banks: dict[str, Bank] = {}

    def bank_for(self, vpa: str) -> Bank:
        handle = vpa_handle(vpa)
        if handle not in self._banks:
            self._banks[handle] = Bank(handle, self.store, self.faults)
        return self._banks[handle]

    def resolve(self, vpa: str) -> dict:
        """VPA directory lookup -- what a payer app does before showing 'Pay to'."""
        acct = self.store.get_account_by_vpa(vpa)
        if acct is None:
            raise UpiError("XH", f"VPA not registered: {vpa}")
        return {
            "vpa": acct.vpa,
            "name": acct.holder_name,
            "bank_handle": acct.bank_handle,
            "type": acct.account_type.value,
        }

    # -- legs --------------------------------------------------------------

    def debit_leg(self, txn: Transaction) -> RailResponse:
        bank = self.bank_for(txn.payer_vpa)
        try:
            code = bank.debit(txn)
            return RailResponse(code, "debit successful", "debit")
        except UpiError as exc:
            return RailResponse(exc.code, exc.message, "debit")

    def credit_leg(self, txn: Transaction) -> RailResponse:
        bank = self.bank_for(txn.payee_vpa)
        try:
            code = bank.credit(txn)
            return RailResponse(code, "credit successful", "credit")
        except UpiError as exc:
            return RailResponse(exc.code, exc.message, "credit")

    def reverse_leg(self, txn: Transaction) -> RailResponse:
        bank = self.bank_for(txn.payer_vpa)
        try:
            code = bank.reverse_debit(txn)
            return RailResponse(code, "reversal successful", "reversal")
        except UpiError as exc:
            return RailResponse(exc.code, exc.message, "reversal")

    # -- reconciliation ----------------------------------------------------

    def inquire(self, txn: Transaction) -> dict:
        """Ask both banks what actually happened. Used by the recon sweep.

        A timed-out transaction is only resolvable by asking the banks -- the
        switch's own record says 'unknown', which is the point.
        """
        payer_bank = self.bank_for(txn.payer_vpa)
        payee_bank = self.bank_for(txn.payee_vpa)
        entries = self.store.ledger_for_txn(txn.txn_id)
        net_suspense = sum(
            e.signed_paise for e in entries if e.account_id == SUSPENSE_ACCOUNT_ID
        )
        return {
            "debit_posted": payer_bank.debit_posted(txn),
            "credit_posted": payee_bank.credit_posted(txn),
            "suspense_balance_paise": net_suspense,
            "entry_count": len(entries),
        }
