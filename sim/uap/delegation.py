"""
Delegation topology -- including the shape UPI Circle cannot express.

UPI Circle is *one primary -> up to five secondaries*, and a secondary may accept
delegation from exactly one primary. A shared household appliance is the inverse:
*many principals -> one agent*. A fridge serving a family of four is, under Circle,
necessarily one person's fridge.

That inversion is the reason this module exists. Once several principals fund one
agent, questions appear that no deployed rail answers:

  - which principal's money pays for a given basket?
  - may a principal scope their delegation to categories, so a teenager's
    delegation funds milk but not alcohol?
  - when one principal revokes, what does the agent retain?
  - what happens to in-flight authority at the moment of revocation?

The resolution policy here is deliberately explicit and boring. It is a policy
question wearing a technical costume, and writing it down is most of the work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .intent import Money
from .mandate import Keypair


class Revocation(str, Enum):
    ACTIVE = "active"
    REVOKED_BY_PRINCIPAL = "revoked_by_principal"
    REVOKED_BY_DEVICE_RESET = "revoked_by_device_reset"
    EXPIRED = "expired"


@dataclass
class Device:
    """
    An agent host: a fridge, a speaker, a phone.

    Assumption A9 -- device identity is distinct from agent identity. A device
    resale or factory reset revokes every delegation bound to it, without touching
    delegations the same principal granted to agents on other devices.
    """

    device_id: str
    key: Keypair
    shared: bool = False
    reset: bool = False

    def factory_reset(self) -> None:
        self.reset = True


@dataclass
class Principal:
    """A human who can grant authority."""

    name: str
    key: Keypair
    #: what this person is willing to expose to agents in total, ever
    account_balance: Money = field(default_factory=lambda: Money.rupees(50_000))

    def __hash__(self) -> int:
        return hash(self.name)


@dataclass
class Delegation:
    """
    One principal's grant to one agent.

    `categories` is the scoping primitive Circle has no equivalent for: full
    delegation there is an amount cap and nothing else.
    """

    principal: Principal
    agent_id: str
    device_id: str
    budget: Money
    spent: Money = field(default_factory=lambda: Money(0))
    categories: frozenset[str] | None = None  # None == unrestricted
    state: Revocation = Revocation.ACTIVE
    #: per-transaction ceiling; UPI Circle's analogue is Rs 5,000
    per_txn_cap: Money = field(default_factory=lambda: Money.rupees(5_000))

    @property
    def remaining(self) -> Money:
        return self.budget - self.spent

    def covers(self, category: str, amount: Money) -> tuple[bool, str]:
        if self.state is not Revocation.ACTIVE:
            return False, f"delegation {self.state.value}"
        if self.categories is not None and category not in self.categories:
            return False, f"category '{category}' outside delegation scope"
        if amount.paise > self.per_txn_cap.paise:
            return False, f"{amount} exceeds per-transaction cap {self.per_txn_cap}"
        if amount.paise > self.remaining.paise:
            return False, f"{amount} exceeds remaining budget {self.remaining}"
        return True, "ok"

    def revoke(self, reason: Revocation = Revocation.REVOKED_BY_PRINCIPAL) -> None:
        self.state = reason


@dataclass
class Agent:
    """
    A registered agent identity, chained to a device and to >=1 principals.

    Assumption A15: the agent may be compromised. Nothing here trusts it. Its key
    proves *which* agent acted, never that the action was legitimate -- that is
    what the mandate chain is for.
    """

    agent_id: str
    key: Keypair
    device: Device
    purpose: str = "general"
    delegations: list[Delegation] = field(default_factory=list)

    def grant(self, principal: Principal, budget: Money,
              categories: frozenset[str] | None = None,
              per_txn_cap: Money | None = None) -> Delegation:
        d = Delegation(
            principal=principal,
            agent_id=self.agent_id,
            device_id=self.device.device_id,
            budget=budget,
            categories=categories,
            per_txn_cap=per_txn_cap or Money.rupees(5_000),
        )
        self.delegations.append(d)
        return d

    # -- the interesting part ------------------------------------------------

    def resolve_funding(self, category: str, amount: Money) -> tuple[Delegation | None, list[str]]:
        """
        Pick which principal pays.

        Policy, stated explicitly because it is a policy and not a fact:

          1. a device reset revokes everything on that device, first;
          2. only ACTIVE delegations whose scope covers the category are eligible;
          3. among eligible ones, prefer the *most narrowly scoped* -- a
             category-scoped grant is a more specific expression of consent than
             an unrestricted one, and should be consumed before it;
          4. tie-break on largest remaining budget, so no single principal is
             drained while another sits unused.

        Rule 3 is arguable and worth arguing about, in both directions. The
        alternative -- spend the unrestricted grant first -- produces a household
        where the least careful member funds everything. But narrowest-first has its
        own pathology: it drains the teenager's Rs 500 dairy grant to buy the
        household's milk before touching either parent's Rs 4,000. Neither rule is
        obviously right, which is the finding. A rail that ships multi-principal
        delegation has to pick one and defend it.
        """
        trace: list[str] = []

        if self.device.reset:
            for d in self.delegations:
                d.revoke(Revocation.REVOKED_BY_DEVICE_RESET)
            trace.append(f"device {self.device.device_id} was reset -- all delegations revoked")
            return None, trace

        eligible: list[Delegation] = []
        for d in self.delegations:
            ok, why = d.covers(category, amount)
            if ok:
                eligible.append(d)
            else:
                trace.append(f"{d.principal.name}: {why}")

        if not eligible:
            return None, trace

        eligible.sort(key=lambda d: (
            len(d.categories) if d.categories is not None else 10**6,  # narrower first
            -d.remaining.paise,                                        # then headroom
        ))
        chosen = eligible[0]
        trace.append(
            f"funded by {chosen.principal.name} "
            f"({'scoped' if chosen.categories is not None else 'unrestricted'}, "
            f"{chosen.remaining} remaining)"
        )
        return chosen, trace


@dataclass
class Household:
    """
    Several principals sharing one or more devices.

    Exists to make the inversion visible: `Household.agents_for(principal)` is
    one-to-many in Circle, and `Agent.delegations` is many-to-one here.
    """

    name: str
    members: list[Principal] = field(default_factory=list)
    devices: list[Device] = field(default_factory=list)
    agents: list[Agent] = field(default_factory=list)

    def principals_funding(self, agent: Agent) -> list[Principal]:
        return [d.principal for d in agent.delegations if d.state is Revocation.ACTIVE]

    def revoke_all_from(self, principal: Principal) -> int:
        """One member withdraws. Everyone else's grants are untouched."""
        n = 0
        for a in self.agents:
            for d in a.delegations:
                if d.principal is principal and d.state is Revocation.ACTIVE:
                    d.revoke()
                    n += 1
        return n
