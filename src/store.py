"""SQLite persistence: accounts, mandates, transactions, ledger, idempotency.

Three invariants the store enforces rather than trusts callers to respect:

  1. **Double entry.** Money is only ever moved through `post_entries`, which
     refuses any set of entries that does not sum to zero. A balance is
     therefore always reproducible from the ledger.
  2. **Legal state transitions.** `update_txn_state` checks the transition
     against the state machine in models.py and raises on an illegal move,
     so a bug in the orchestrator surfaces immediately instead of writing an
     impossible row.
  3. **Idempotency.** A repeated idempotency key returns the original
     transaction instead of creating a second one. Payment clients retry;
     without this, a retry is a double charge.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

from core import Money, new_id, validate_vpa, vpa_handle
from models import (
    Account,
    AccountType,
    Direction,
    LedgerEntry,
    Mandate,
    MandateStatus,
    Transaction,
    TxnState,
    can_transition,
    utcnow,
)

SUSPENSE_ACCOUNT_ID = "acct_upi_suspense"

# Opening balances are posted as real ledger entries against this account
# rather than written straight to `accounts.balance`. That keeps the ledger
# the complete source of truth: every balance in the system is exactly the sum
# of its entries, and the global ledger nets to zero. Reconciliation would
# otherwise need a special case for money that appeared from nowhere.
FUNDING_ACCOUNT_ID = "acct_bank_funding"

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    account_id   TEXT PRIMARY KEY,
    vpa          TEXT UNIQUE NOT NULL,
    holder_name  TEXT NOT NULL,
    bank_handle  TEXT NOT NULL,
    account_type TEXT NOT NULL,
    balance      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS mandates (
    umn                TEXT PRIMARY KEY,
    payer_vpa          TEXT NOT NULL,
    allowed_payees     TEXT NOT NULL,
    max_amount_per_txn INTEGER NOT NULL,
    total_cap          INTEGER NOT NULL,
    consumed           INTEGER NOT NULL,
    valid_from         TEXT NOT NULL,
    valid_until        TEXT NOT NULL,
    status             TEXT NOT NULL,
    purpose            TEXT NOT NULL,
    created_at         TEXT NOT NULL,
    agent_id           TEXT,
    categories         TEXT,
    rail               TEXT,
    period_cap         INTEGER,
    period_days        INTEGER,
    period_started_at  TEXT,
    period_consumed    INTEGER
);

CREATE TABLE IF NOT EXISTS agents (
    agent_id      TEXT PRIMARY KEY,
    agent_did     TEXT NOT NULL,
    owner_vpa     TEXT NOT NULL,
    owner_did     TEXT NOT NULL,
    device_id     TEXT NOT NULL,
    status_index  INTEGER NOT NULL,
    token         TEXT NOT NULL,
    issued_at     TEXT NOT NULL,
    expires_at    TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    txn_id          TEXT PRIMARY KEY,
    upi_txn_id      TEXT NOT NULL,
    rrn             TEXT UNIQUE NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL,
    payer_vpa       TEXT NOT NULL,
    payee_vpa       TEXT NOT NULL,
    amount          INTEGER NOT NULL,
    state           TEXT NOT NULL,
    response_code   TEXT,
    umn             TEXT,
    note            TEXT NOT NULL,
    attempts        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    agent_id        TEXT
);

CREATE TABLE IF NOT EXISTS ledger (
    entry_id   TEXT PRIMARY KEY,
    txn_id     TEXT NOT NULL,
    account_id TEXT NOT NULL,
    direction  TEXT NOT NULL,
    amount     INTEGER NOT NULL,
    narrative  TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    event_id   TEXT PRIMARY KEY,
    txn_id     TEXT,
    kind       TEXT NOT NULL,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ledger_txn ON ledger(txn_id);
CREATE INDEX IF NOT EXISTS idx_ledger_acct ON ledger(account_id);
CREATE INDEX IF NOT EXISTS idx_txn_state ON transactions(state);
CREATE INDEX IF NOT EXISTS idx_events_txn ON events(txn_id);
"""


def _parse_dt(raw: str) -> datetime:
    dt = datetime.fromisoformat(raw)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class Store:
    def __init__(self, path: str = "upi_sim.db"):
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()
        self._migrate()
        self._ensure_system_accounts()

    # -- migration ---------------------------------------------------------

    #: table -> columns added after that table's first release. `CREATE TABLE IF
    #: NOT EXISTS` does nothing to a table that already exists, so a database
    #: written before these columns existed would keep working right up until the
    #: first query that mentions one.
    _ADDED_COLUMNS = {
        "transactions": {"agent_id": "TEXT"},
        "mandates": {
            "agent_id": "TEXT",
            "categories": "TEXT",
            "rail": "TEXT",
            "period_cap": "INTEGER",
            "period_days": "INTEGER",
            "period_started_at": "TEXT",
            "period_consumed": "INTEGER",
        },
    }

    def _migrate(self) -> None:
        """Add columns an older database is missing. Safe to run every startup."""
        with self._lock:
            for table, columns in self._ADDED_COLUMNS.items():
                present = {
                    row["name"]
                    for row in self._conn.execute(f"PRAGMA table_info({table})")
                }
                if not present:                # table not created yet
                    continue
                for name, decl in columns.items():
                    if name not in present:
                        self._conn.execute(
                            f"ALTER TABLE {table} ADD COLUMN {name} {decl}"
                        )
            self._conn.commit()

    # -- lifecycle ---------------------------------------------------------

    def close(self):
        self._conn.close()

    @classmethod
    def fresh(cls, path: str = "upi_sim.db") -> "Store":
        """Delete any existing database and start clean."""
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(path + suffix)
            except FileNotFoundError:
                pass
        return cls(path)

    def _ensure_system_accounts(self):
        for account_id, vpa, name in (
            (FUNDING_ACCOUNT_ID, "funding@upisim", "Bank Funding (contra)"),
            (SUSPENSE_ACCOUNT_ID, "suspense@upisim", "UPI Settlement Suspense"),
        ):
            if self.get_account(account_id) is None:
                self._insert_account(
                    Account(
                        account_id=account_id, vpa=vpa, holder_name=name,
                        bank_handle=vpa_handle(vpa),
                        account_type=AccountType.SUSPENSE, balance=Money.zero(),
                    )
                )

    # -- accounts ----------------------------------------------------------

    def _insert_account(self, acct: Account) -> Account:
        with self._lock:
            self._conn.execute(
                "INSERT INTO accounts VALUES (?,?,?,?,?,?)",
                (
                    acct.account_id, acct.vpa, acct.holder_name,
                    acct.bank_handle, acct.account_type.value, acct.balance.paise,
                ),
            )
            self._conn.commit()
        return acct

    def create_account(
        self,
        vpa: str,
        holder_name: str,
        account_type: AccountType,
        opening_balance: Money,
        account_id: str | None = None,
    ) -> Account:
        """Open an account, funding it through the ledger rather than by fiat."""
        vpa = validate_vpa(vpa)
        acct = self._insert_account(
            Account(
                account_id=account_id or new_id("acct"),
                vpa=vpa,
                holder_name=holder_name,
                bank_handle=vpa_handle(vpa),
                account_type=account_type,
                balance=Money.zero(),
            )
        )
        if opening_balance.is_positive:
            self.post_entries([
                LedgerEntry(
                    entry_id=new_id("led"), txn_id=f"opening:{acct.account_id}",
                    account_id=FUNDING_ACCOUNT_ID, direction=Direction.DEBIT,
                    amount=opening_balance, narrative=f"Opening float for {vpa}",
                ),
                LedgerEntry(
                    entry_id=new_id("led"), txn_id=f"opening:{acct.account_id}",
                    account_id=acct.account_id, direction=Direction.CREDIT,
                    amount=opening_balance, narrative="Opening balance",
                ),
            ])
            acct = self.get_account(acct.account_id)
        return acct

    def _row_to_account(self, row: sqlite3.Row) -> Account:
        return Account(
            account_id=row["account_id"],
            vpa=row["vpa"],
            holder_name=row["holder_name"],
            bank_handle=row["bank_handle"],
            account_type=AccountType(row["account_type"]),
            balance=Money(row["balance"]),
        )

    def get_account(self, account_id: str) -> Account | None:
        row = self._conn.execute(
            "SELECT * FROM accounts WHERE account_id=?", (account_id,)
        ).fetchone()
        return self._row_to_account(row) if row else None

    def get_account_by_vpa(self, vpa: str) -> Account | None:
        row = self._conn.execute(
            "SELECT * FROM accounts WHERE vpa=?", (validate_vpa(vpa),)
        ).fetchone()
        return self._row_to_account(row) if row else None

    def get_account_by_vpa_safe(self, vpa: str) -> Account | None:
        """Like get_account_by_vpa, but returns None for a malformed VPA.

        For API path parameters, where a bad VPA should be a 404 rather than
        an unhandled ValueError surfacing as a 500.
        """
        try:
            return self.get_account_by_vpa(vpa)
        except ValueError:
            return None

    def list_accounts(self) -> list[Account]:
        rows = self._conn.execute("SELECT * FROM accounts ORDER BY account_type, vpa")
        return [self._row_to_account(r) for r in rows]

    # -- ledger ------------------------------------------------------------

    def post_entries(self, entries: list[LedgerEntry]) -> None:
        """Atomically post a balanced set of entries and move the balances.

        Rejects an unbalanced set. This is the single write path for money --
        nothing else in the codebase updates `accounts.balance`.
        """
        if not entries:
            raise ValueError("no entries to post")
        total = sum(e.signed_paise for e in entries)
        if total != 0:
            raise ValueError(
                f"unbalanced ledger posting: entries sum to {total} paise, expected 0"
            )

        with self._lock:
            try:
                cur = self._conn.cursor()
                for e in entries:
                    cur.execute(
                        "INSERT INTO ledger VALUES (?,?,?,?,?,?,?)",
                        (
                            e.entry_id, e.txn_id, e.account_id, e.direction.value,
                            e.amount.paise, e.narrative, e.created_at.isoformat(),
                        ),
                    )
                    cur.execute(
                        "UPDATE accounts SET balance = balance + ? WHERE account_id = ?",
                        (e.signed_paise, e.account_id),
                    )
                    if cur.rowcount != 1:
                        raise ValueError(f"no such account: {e.account_id}")
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def ledger_for_txn(self, txn_id: str) -> list[LedgerEntry]:
        rows = self._conn.execute(
            "SELECT * FROM ledger WHERE txn_id=? ORDER BY created_at, entry_id", (txn_id,)
        )
        return [self._row_to_entry(r) for r in rows]

    def all_ledger_entries(self) -> list[LedgerEntry]:
        rows = self._conn.execute("SELECT * FROM ledger ORDER BY created_at, entry_id")
        return [self._row_to_entry(r) for r in rows]

    def _row_to_entry(self, row: sqlite3.Row) -> LedgerEntry:
        return LedgerEntry(
            entry_id=row["entry_id"],
            txn_id=row["txn_id"],
            account_id=row["account_id"],
            direction=Direction(row["direction"]),
            amount=Money(row["amount"]),
            narrative=row["narrative"],
            created_at=_parse_dt(row["created_at"]),
        )

    # -- mandates ----------------------------------------------------------

    def save_mandate(self, m: Mandate) -> Mandate:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO mandates ("
                "  umn, payer_vpa, allowed_payees, max_amount_per_txn, total_cap,"
                "  consumed, valid_from, valid_until, status, purpose, created_at,"
                "  agent_id, categories, rail, period_cap, period_days,"
                "  period_started_at, period_consumed"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    m.umn, m.payer_vpa, json.dumps(m.allowed_payees),
                    m.max_amount_per_txn.paise, m.total_cap.paise, m.consumed.paise,
                    m.valid_from.isoformat(), m.valid_until.isoformat(),
                    m.status.value, m.purpose, m.created_at.isoformat(),
                    m.agent_id, json.dumps(m.categories), m.rail,
                    m.period_cap.paise if m.period_cap else None,
                    m.period_days,
                    m.period_started_at.isoformat() if m.period_started_at else None,
                    m.period_consumed.paise,
                ),
            )
            self._conn.commit()
        return m

    def _row_to_mandate(self, row: sqlite3.Row) -> Mandate:
        return Mandate(
            umn=row["umn"],
            payer_vpa=row["payer_vpa"],
            allowed_payees=json.loads(row["allowed_payees"]),
            max_amount_per_txn=Money(row["max_amount_per_txn"]),
            total_cap=Money(row["total_cap"]),
            consumed=Money(row["consumed"]),
            valid_from=_parse_dt(row["valid_from"]),
            valid_until=_parse_dt(row["valid_until"]),
            status=MandateStatus(row["status"]),
            purpose=row["purpose"],
            created_at=_parse_dt(row["created_at"]),
            agent_id=row["agent_id"],
            categories=json.loads(row["categories"]) if row["categories"] else [],
            rail=row["rail"],
            period_cap=(
                Money(row["period_cap"]) if row["period_cap"] is not None else None
            ),
            period_days=row["period_days"],
            period_started_at=(
                _parse_dt(row["period_started_at"])
                if row["period_started_at"] else None
            ),
            period_consumed=Money(row["period_consumed"] or 0),
        )

    def get_mandate(self, umn: str) -> Mandate | None:
        row = self._conn.execute("SELECT * FROM mandates WHERE umn=?", (umn,)).fetchone()
        return self._row_to_mandate(row) if row else None

    def list_mandates(self, payer_vpa: str | None = None) -> list[Mandate]:
        if payer_vpa:
            rows = self._conn.execute(
                "SELECT * FROM mandates WHERE payer_vpa=? ORDER BY created_at DESC",
                (validate_vpa(payer_vpa),),
            )
        else:
            rows = self._conn.execute("SELECT * FROM mandates ORDER BY created_at DESC")
        return [self._row_to_mandate(r) for r in rows]

    def consume_mandate(self, umn: str, amount: Money) -> Mandate:
        """Record spend against a mandate, marking it exhausted when used up.

        The rolling period is consumed here too, and rolls over first if its window
        has closed. Rolling over at spend time rather than on a timer means there is
        no scheduler to go wrong: the window is whatever the arithmetic says it is.
        """
        with self._lock:
            m = self.get_mandate(umn)
            if m is None:
                raise ValueError(f"no such mandate: {umn}")

            if m.period_cap is not None:
                if m.period_elapsed() or m.period_started_at is None:
                    m.period_started_at = utcnow()
                    m.period_consumed = Money.zero()
                m.period_consumed = m.period_consumed + amount

            m.consumed = m.consumed + amount
            if m.remaining.paise <= 0:
                m.status = MandateStatus.EXHAUSTED
            return self.save_mandate(m)

    def release_mandate(self, umn: str, amount: Money) -> Mandate:
        """Give back headroom when a consumed transaction is reversed."""
        with self._lock:
            m = self.get_mandate(umn)
            if m is None:
                raise ValueError(f"no such mandate: {umn}")
            m.consumed = m.consumed - amount
            if m.consumed.paise < 0:
                m.consumed = Money.zero()
            if m.period_cap is not None:
                m.period_consumed = m.period_consumed - amount
                if m.period_consumed.paise < 0:
                    m.period_consumed = Money.zero()
            if m.status is MandateStatus.EXHAUSTED and m.remaining.is_positive:
                m.status = MandateStatus.ACTIVE
            return self.save_mandate(m)

    def set_mandate_status(self, umn: str, status: MandateStatus) -> Mandate:
        with self._lock:
            m = self.get_mandate(umn)
            if m is None:
                raise ValueError(f"no such mandate: {umn}")
            m.status = status
            return self.save_mandate(m)

    # -- agents ------------------------------------------------------------
    #
    # The credential is stored as its signed token, not as parsed fields. The
    # fields are there to query on; the token is the evidence, and re-serialising
    # a credential from columns would produce bytes the owner never signed.

    def save_registration(self, reg) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO agents ("
                "  agent_id, agent_did, owner_vpa, owner_did, device_id,"
                "  status_index, token, issued_at, expires_at"
                ") VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    reg.agent_id, reg.agent_did, reg.owner_vpa, reg.owner_did,
                    reg.device_id, reg.status_index, reg.token,
                    reg.issued_at.isoformat(),
                    reg.expires_at.isoformat() if reg.expires_at else None,
                ),
            )
            self._conn.commit()

    def get_registration(self, agent_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM agents WHERE agent_id=?", (agent_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_registrations(self, device_id: str | None = None) -> list[dict]:
        if device_id:
            rows = self._conn.execute(
                "SELECT * FROM agents WHERE device_id=? ORDER BY issued_at",
                (device_id,),
            )
        else:
            rows = self._conn.execute("SELECT * FROM agents ORDER BY issued_at")
        return [dict(r) for r in rows]

    # -- transactions ------------------------------------------------------

    def create_txn(self, txn: Transaction) -> Transaction:
        with self._lock:
            # Columns are named rather than positional. A positional INSERT breaks
            # the moment anyone adds a column, and breaks silently if the new one
            # happens to be type-compatible with its neighbour.
            self._conn.execute(
                "INSERT INTO transactions ("
                "  txn_id, upi_txn_id, rrn, idempotency_key, payer_vpa, payee_vpa,"
                "  amount, state, response_code, umn, note, attempts,"
                "  created_at, updated_at, agent_id"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    txn.txn_id, txn.upi_txn_id, txn.rrn, txn.idempotency_key,
                    txn.payer_vpa, txn.payee_vpa, txn.amount.paise, txn.state.value,
                    txn.response_code, txn.umn, txn.note, txn.attempts,
                    txn.created_at.isoformat(), txn.updated_at.isoformat(),
                    txn.agent_id,
                ),
            )
            self._conn.commit()
        return txn

    def _row_to_txn(self, row: sqlite3.Row) -> Transaction:
        return Transaction(
            txn_id=row["txn_id"],
            upi_txn_id=row["upi_txn_id"],
            rrn=row["rrn"],
            idempotency_key=row["idempotency_key"],
            payer_vpa=row["payer_vpa"],
            payee_vpa=row["payee_vpa"],
            amount=Money(row["amount"]),
            state=TxnState(row["state"]),
            response_code=row["response_code"],
            umn=row["umn"],
            note=row["note"],
            attempts=row["attempts"],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
            agent_id=row["agent_id"],
        )

    def get_txn(self, txn_id: str) -> Transaction | None:
        row = self._conn.execute(
            "SELECT * FROM transactions WHERE txn_id=?", (txn_id,)
        ).fetchone()
        return self._row_to_txn(row) if row else None

    def get_txn_by_idempotency_key(self, key: str) -> Transaction | None:
        row = self._conn.execute(
            "SELECT * FROM transactions WHERE idempotency_key=?", (key,)
        ).fetchone()
        return self._row_to_txn(row) if row else None

    def list_txns(self, state: TxnState | None = None, limit: int = 100) -> list[Transaction]:
        if state:
            rows = self._conn.execute(
                "SELECT * FROM transactions WHERE state=? ORDER BY created_at DESC LIMIT ?",
                (state.value, limit),
            )
        else:
            rows = self._conn.execute(
                "SELECT * FROM transactions ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        return [self._row_to_txn(r) for r in rows]

    def list_txns_in_states(self, states: list[TxnState]) -> list[Transaction]:
        marks = ",".join("?" for _ in states)
        rows = self._conn.execute(
            f"SELECT * FROM transactions WHERE state IN ({marks}) ORDER BY created_at",
            [s.value for s in states],
        )
        return [self._row_to_txn(r) for r in rows]

    def update_txn_state(
        self,
        txn_id: str,
        new_state: TxnState,
        response_code: str | None = None,
        bump_attempts: bool = False,
    ) -> Transaction:
        with self._lock:
            txn = self.get_txn(txn_id)
            if txn is None:
                raise ValueError(f"no such transaction: {txn_id}")
            if txn.state is not new_state and not can_transition(txn.state, new_state):
                raise ValueError(
                    f"illegal transition {txn.state.value} -> {new_state.value} "
                    f"for {txn_id}"
                )
            txn.state = new_state
            if response_code is not None:
                txn.response_code = response_code
            if bump_attempts:
                txn.attempts += 1
            txn.updated_at = utcnow()
            self._conn.execute(
                "UPDATE transactions SET state=?, response_code=?, attempts=?, updated_at=? "
                "WHERE txn_id=?",
                (
                    txn.state.value, txn.response_code, txn.attempts,
                    txn.updated_at.isoformat(), txn.txn_id,
                ),
            )
            self._conn.commit()
        return txn

    # -- events (audit trail) ---------------------------------------------

    def record_event(self, kind: str, payload: dict, txn_id: str | None = None) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO events VALUES (?,?,?,?,?)",
                (
                    new_id("evt"), txn_id, kind,
                    json.dumps(payload, default=str), utcnow().isoformat(),
                ),
            )
            self._conn.commit()

    def list_events(self, txn_id: str | None = None, limit: int = 200) -> list[dict]:
        if txn_id:
            rows = self._conn.execute(
                "SELECT * FROM events WHERE txn_id=? ORDER BY created_at LIMIT ?",
                (txn_id, limit),
            )
        else:
            rows = self._conn.execute(
                "SELECT * FROM events ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        return [
            {
                "event_id": r["event_id"],
                "txn_id": r["txn_id"],
                "kind": r["kind"],
                "payload": json.loads(r["payload"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]
