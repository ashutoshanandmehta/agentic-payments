"""Reconciliation: resolve timed-out transactions and audit the ledger.

A payment that timed out is not failed and not successful -- the switch simply
does not know. The only way to resolve it is to ask the banks what actually
posted, which is what `sweep` does:

    debit posted, credit posted      -> complete it, mark SETTLED
    debit posted, no credit          -> reverse it, return the money
    nothing posted                   -> nothing to undo, mark FAILED

Real switches run this on a cycle (UPI's is the TCC/URCS flow). Here it is a
callable so a demo can trigger it and watch stuck money resolve.

`audit` is the independent check: it re-derives every balance from the ledger
and verifies the books balance globally. If it ever disagrees with the
`accounts` table, the bug is in a write path, not in the audit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from core import Money
from models import TxnState, utcnow
from store import SUSPENSE_ACCOUNT_ID, Store
from rails import Switch

STUCK_STATES = [TxnState.TIMED_OUT, TxnState.DEBITED, TxnState.CREDIT_PENDING]


@dataclass
class ReconOutcome:
    txn_id: str
    action: str                     # completed | reversed | failed | skipped
    detail: str

    def to_dict(self) -> dict:
        return {"txn_id": self.txn_id, "action": self.action, "detail": self.detail}


@dataclass
class ReconReport:
    scanned: int = 0
    outcomes: list[ReconOutcome] = field(default_factory=list)

    def add(self, outcome: ReconOutcome):
        self.outcomes.append(outcome)

    @property
    def counts(self) -> dict:
        out: dict[str, int] = {}
        for o in self.outcomes:
            out[o.action] = out.get(o.action, 0) + 1
        return out

    def to_dict(self) -> dict:
        return {
            "scanned": self.scanned,
            "counts": self.counts,
            "outcomes": [o.to_dict() for o in self.outcomes],
        }


class Reconciler:
    def __init__(self, store: Store, switch: Switch, stale_after_seconds: int = 0):
        self.store = store
        self.switch = switch
        self.stale_after_seconds = stale_after_seconds

    # ----------------------------------------------------------------------

    def sweep(self) -> ReconReport:
        """Resolve every stuck transaction by asking the banks what posted."""
        report = ReconReport()
        cutoff = utcnow() - timedelta(seconds=self.stale_after_seconds)

        for txn in self.store.list_txns_in_states(STUCK_STATES):
            report.scanned += 1
            if txn.updated_at > cutoff:
                report.add(ReconOutcome(txn.txn_id, "skipped", "not stale yet"))
                continue

            # Faults must not fire against a recovery attempt, or the sweep
            # can inject the very failure it is trying to resolve.
            saved_force = self.switch.faults.force
            self.switch.faults.force = None
            try:
                report.add(self._resolve(txn))
            finally:
                self.switch.faults.force = saved_force

        self.store.record_event("recon.sweep", report.to_dict())
        return report

    def _resolve(self, txn) -> ReconOutcome:
        state = self.switch.inquire(txn)
        self.store.record_event("recon.inquiry", state, txn.txn_id)

        if state["debit_posted"] and state["credit_posted"]:
            # Both legs landed; only the bookkeeping is behind.
            if txn.state is not TxnState.CREDITED:
                self.store.update_txn_state(txn.txn_id, TxnState.CREDITED, "00")
            self.store.update_txn_state(txn.txn_id, TxnState.SETTLED, "00")
            self.store.record_event("recon.completed", state, txn.txn_id)
            return ReconOutcome(txn.txn_id, "completed", "both legs posted; settled")

        if state["debit_posted"] and not state["credit_posted"]:
            rev = self.switch.reverse_leg(txn)
            self.store.record_event("recon.reversal", rev.to_dict(), txn.txn_id)
            if not rev.ok:
                self.store.update_txn_state(txn.txn_id, TxnState.FAILED, rev.code)
                return ReconOutcome(txn.txn_id, "failed", f"reversal failed [{rev.code}]")
            self.store.update_txn_state(txn.txn_id, TxnState.REVERSED, "U31")
            if txn.umn:
                self.store.release_mandate(txn.umn, txn.amount)
            return ReconOutcome(
                txn.txn_id, "reversed", "debit posted without credit; funds returned"
            )

        self.store.update_txn_state(txn.txn_id, TxnState.FAILED, txn.response_code or "U30")
        return ReconOutcome(txn.txn_id, "failed", "no legs posted; nothing to undo")

    # ----------------------------------------------------------------------

    def audit(self) -> dict:
        """Re-derive every balance from the ledger and check the books.

        Four independent assertions. Opening balances are posted through the
        funding account, so the ledger alone accounts for every paisa and
        none of these needs a special case:

          * every transaction's entries net to zero
          * the global ledger nets to zero
          * each account's stored balance equals the sum of its entries
          * the suspense account is empty (nothing stuck mid-flight)
        """
        entries = self.store.all_ledger_entries()

        per_txn: dict[str, int] = {}
        per_account: dict[str, int] = {}
        for e in entries:
            per_txn[e.txn_id] = per_txn.get(e.txn_id, 0) + e.signed_paise
            per_account[e.account_id] = per_account.get(e.account_id, 0) + e.signed_paise

        unbalanced_txns = [
            {"txn_id": t, "net_paise": v} for t, v in per_txn.items() if v != 0
        ]

        drift = []
        for acct in self.store.list_accounts():
            derived = per_account.get(acct.account_id, 0)
            if derived != acct.balance.paise:
                drift.append({
                    "account_id": acct.account_id,
                    "vpa": acct.vpa,
                    "stored_balance_paise": acct.balance.paise,
                    "ledger_derived_paise": derived,
                    "difference_paise": acct.balance.paise - derived,
                })

        global_net = sum(per_account.values())
        suspense = per_account.get(SUSPENSE_ACCOUNT_ID, 0)
        healthy = (
            global_net == 0 and not unbalanced_txns and not drift and suspense == 0
        )

        return {
            "entry_count": len(entries),
            "transaction_count": len(per_txn),
            "global_net_paise": global_net,
            "global_balanced": global_net == 0,
            "unbalanced_transactions": unbalanced_txns,
            "balance_drift": drift,
            "suspense_balance_paise": suspense,
            "suspense_clear": suspense == 0,
            "in_flight": Money(suspense).to_rupees_str(),
            "healthy": healthy,
        }
