"""
A settlement ledger for the primitive UPI does not currently have.

UPI Autopay is fixed-payee. UPI Reserve Pay blocks funds *per merchant*. Both bind
a payee at mandate creation -- before a comparison agent has decided anything. A
delegated grocery agent cannot name its payee in advance; naming it is the whole
job it was delegated to do.

So this ledger models the missing shape: a **cross-merchant reservation**. Funds
are blocked against the principal's account, and captured against whichever
merchant wins, up to the reserved amount, until the reservation expires or is
released.

If UAP ships still binding a payee at creation, this file is the diff -- the
concrete statement of what would have to change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .intent import Money


class ReservationState(str, Enum):
    OPEN = "open"
    EXHAUSTED = "exhausted"
    RELEASED = "released"
    REVOKED = "revoked"


@dataclass
class Capture:
    merchant: str
    amount: Money
    payment_ref: str


@dataclass
class Reservation:
    """Blocked funds, not yet paid to anyone in particular."""

    reservation_id: str
    principal: str
    amount: Money
    captured: list[Capture] = field(default_factory=list)
    state: ReservationState = ReservationState.OPEN

    @property
    def captured_total(self) -> Money:
        return Money(sum(c.amount.paise for c in self.captured))

    @property
    def available(self) -> Money:
        return self.amount - self.captured_total

    def capture(self, merchant: str, amount: Money, payment_ref: str) -> tuple[bool, str]:
        if self.state is not ReservationState.OPEN:
            return False, f"reservation is {self.state.value}"
        if amount.paise > self.available.paise:
            return False, f"{amount} exceeds available {self.available}"
        self.captured.append(Capture(merchant, amount, payment_ref))
        if self.available.paise == 0:
            self.state = ReservationState.EXHAUSTED
        return True, "captured"

    def release(self) -> Money:
        """Unblock whatever is left. Instant, per Reserve Pay's own behaviour."""
        left = self.available
        self.state = ReservationState.RELEASED
        return left

    def revoke(self) -> Money:
        left = self.available
        self.state = ReservationState.REVOKED
        return left


@dataclass
class Ledger:
    balances: dict[str, Money] = field(default_factory=dict)
    reservations: dict[str, Reservation] = field(default_factory=dict)
    _seq: int = 0

    def open_account(self, principal: str, balance: Money) -> None:
        self.balances[principal] = balance

    def reserve(self, principal: str, amount: Money) -> tuple[Reservation | None, str]:
        bal = self.balances.get(principal, Money(0))
        if amount.paise > bal.paise:
            return None, f"insufficient balance: {bal} < {amount}"
        self._seq += 1
        rid = f"RES{self._seq:04d}"
        self.balances[principal] = bal - amount
        res = Reservation(rid, principal, amount)
        self.reservations[rid] = res
        return res, "reserved"

    def release(self, reservation_id: str) -> Money:
        res = self.reservations[reservation_id]
        back = res.release()
        self.balances[res.principal] = self.balances[res.principal] + back
        return back

    def settle_report(self) -> list[str]:
        out = []
        for rid, res in self.reservations.items():
            out.append(
                f"  {rid}  {res.principal:<8} reserved {res.amount}  "
                f"captured {res.captured_total}  available {res.available}  [{res.state.value}]"
            )
            for c in res.captured:
                out.append(f"        -> {c.merchant}: {c.amount} ({c.payment_ref})")
        return out
