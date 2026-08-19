"""Wiring: build a fully-configured simulator from one call.

Both the CLI and the REST API construct the world through here, so there is
exactly one definition of how the pieces fit together.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from consent import Keypair, OrderSigner
from core import Money
from models import AccountType, utcnow
from policy import PolicyConfig, PolicyEngine
from rails import FaultConfig, Switch
from recon import Reconciler
from orchestrator import Orchestrator
from store import Store

DEFAULT_DB = "upi_sim.db"

USER_VPA = "ashutosh@okhdfc"
MERCHANT_VPA = "brewhouse@ybl"
SECOND_MERCHANT_VPA = "cloudhost@okaxis"


@dataclass
class Simulator:
    store: Store
    switch: Switch
    policy: PolicyEngine
    orchestrator: Orchestrator
    reconciler: Reconciler
    faults: FaultConfig
    agent_key: "Keypair | None" = None
    merchant_keys: dict | None = None

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

    # Keys for the order gate. In a real system the switch would hold registered
    # public keys; here it holds the keypairs, since there is nobody to attack it.
    agent_key = Keypair("agent:subscriptions")
    merchant_keys = {
        MERCHANT_VPA: Keypair(MERCHANT_VPA),
        SECOND_MERCHANT_VPA: Keypair(SECOND_MERCHANT_VPA),
    }
    policy = PolicyEngine(store, policy_config, agent_key=agent_key,
                          merchant_keys=merchant_keys, order_signer=order_signer)
    orchestrator = Orchestrator(store, switch, policy)
    reconciler = Reconciler(store, switch)
    return Simulator(store, switch, policy, orchestrator, reconciler, faults,
                     agent_key, merchant_keys)


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
    )

    return {
        "user": user.to_dict(),
        "merchant": merchant.to_dict(),
        "other_merchant": other.to_dict(),
        "mandate": mandate.to_dict(),
        "standing_instruction": STANDING_INSTRUCTION,
    }
