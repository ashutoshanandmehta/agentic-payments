"""Wiring: build a fully-configured simulator from one call.

Both the CLI and the REST API construct the world through here, so there is
exactly one definition of how the pieces fit together.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from consent import Keypair, OrderSigner
from identity import Resolver
from registration import AgentRegistry
from core import Money
from models import AccountType, utcnow
from policy import PolicyConfig, PolicyEngine
from rails import FaultConfig, Switch
from recon import Reconciler
from orchestrator import Orchestrator
from store import Store

DEFAULT_DB = "upi_sim.db"

USER_VPA = "ashutosh@okhdfc"
#: the owner's own card. the second way to fund an agent, alongside their bank.
USER_CARD_VPA = "ashutosh@okhdfccard"
MERCHANT_VPA = "brewhouse@ybl"
SECOND_MERCHANT_VPA = "cloudhost@okaxis"

#: the appliance the agent runs on. Several agents may share one.
DEVICE_ID = "appliance-kitchen-01"


@dataclass
class Simulator:
    """The world, wired together.

    Note which parties hold what. `agent_key` and `merchant_keys` are **private**
    keys, held by the parties that sign with them -- that is legitimate, because an
    agent really does hold its own key. `resolver` holds only the public halves, and
    it is the one the policy engine gets. Nothing that reaches a verdict holds a
    secret belonging to somebody it is judging.
    """

    store: Store
    switch: Switch
    policy: PolicyEngine
    orchestrator: Orchestrator
    reconciler: Reconciler
    faults: FaultConfig
    agent_key: "Keypair | None" = None
    merchant_keys: dict | None = None
    resolver: "Resolver | None" = None
    owner_key: "Keypair | None" = None
    registry: "AgentRegistry | None" = None

    @property
    def agent_name(self) -> str:
        return self.agent_key.label if self.agent_key else ""

    def close(self):
        self.store.close()


def build(
    db_path: str = DEFAULT_DB,
    fresh: bool = False,
    faults: FaultConfig | None = None,
    policy_config: PolicyConfig | None = None,
    order_signer: OrderSigner = OrderSigner.AGENT,
) -> Simulator:
    store = Store.fresh(db_path) if fresh else Store(db_path)
    faults = faults or FaultConfig()
    switch = Switch(store, faults)

    # Private keys stay with the parties that sign: the agent holds its own, each
    # merchant holds its own. The switch is onboarded with the public halves only,
    # which is what `resolver` is -- registering a Signer keeps `.public` and
    # discards the rest.
    agent_key = Keypair("agent:subscriptions")
    merchant_keys = {
        MERCHANT_VPA: Keypair(MERCHANT_VPA),
        SECOND_MERCHANT_VPA: Keypair(SECOND_MERCHANT_VPA),
    }

    resolver = Resolver()
    resolver.register(agent_key.label, agent_key)
    for vpa, key in merchant_keys.items():
        resolver.register(vpa, key)

    # The owner is a separate party from the agent, and that separation is the
    # whole point of a registration: the agent cannot vouch for itself.
    owner_key = Keypair("owner:ashutosh")
    registry = AgentRegistry(owner_key, USER_VPA, resolver=resolver)
    registration = registry.register_agent(agent_key, device_id=DEVICE_ID)
    store.save_registration(registration)

    policy = PolicyEngine(store, policy_config, resolver=resolver,
                          agent_name=agent_key.label, order_signer=order_signer)
    orchestrator = Orchestrator(store, switch, policy)
    reconciler = Reconciler(store, switch)
    return Simulator(store, switch, policy, orchestrator, reconciler, faults,
                     agent_key, merchant_keys, resolver, owner_key, registry)


# --------------------------------------------------------------------------
# Demo world
# --------------------------------------------------------------------------

STANDING_INSTRUCTION = (
    "Pay subscription invoices from Brewhouse Coffee automatically, as long as "
    "the invoice is for the monthly plan and is under 1000 rupees. Do not pay "
    "anything else."
)


def _get_or_create(sim: Simulator, vpa, name, acct_type, opening):
    """Idempotent so `seed` can be re-run against an existing database."""
    existing = sim.store.get_account_by_vpa(vpa)
    if existing is not None:
        return existing
    return sim.store.create_account(
        vpa=vpa, holder_name=name, account_type=acct_type, opening_balance=opening,
    )


def seed(sim: Simulator) -> dict:
    """Create the demo accounts and a scoped mandate for the agent."""
    user = _get_or_create(sim, USER_VPA, "Ashutosh Anand",
                          AccountType.USER, Money.rupees("10000"))
    user_card = _get_or_create(sim, USER_CARD_VPA, "Ashutosh Anand (card)",
                               AccountType.USER_CARD, Money.rupees("10000"))
    merchant = _get_or_create(sim, MERCHANT_VPA, "Brewhouse Coffee Pvt Ltd",
                              AccountType.MERCHANT, Money.rupees("0"))
    other = _get_or_create(sim, SECOND_MERCHANT_VPA, "CloudHost Systems",
                           AccountType.MERCHANT, Money.rupees("0"))

    now = utcnow()
    mandate = sim.orchestrator.create_mandate(
        payer_vpa=USER_VPA,
        allowed_payees=[MERCHANT_VPA],          # note: CloudHost is deliberately out of scope
        max_amount_per_txn=Money.rupees("1000"),
        total_cap=Money.rupees("5000"),
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=365),
        purpose="Brewhouse Coffee monthly subscription",
        agent_id=sim.agent_name,
    )

    return {
        "user": user.to_dict(),
        "user_card": user_card.to_dict(),
        "merchant": merchant.to_dict(),
        "other_merchant": other.to_dict(),
        "mandate": mandate.to_dict(),
        "standing_instruction": STANDING_INSTRUCTION,
        "agent": sim.registry.get(sim.agent_name).to_dict() if sim.registry else None,
    }
