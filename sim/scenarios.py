"""
Scenarios.

Each one declares what it expects *before* it runs, and the harness reports the
mismatch. A scenario that authorises when it should have denied is a finding, not
a bug to be quietly fixed -- it is the simulation earning its keep.

Two families:

  ADVERSARIAL   a merchant, or the agent itself, misbehaves. Does the mandate
                chain catch it, and on which check?
  DELEGATION    the multi-principal household. Whose money pays, and what
                survives a revocation?
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable

from .agent.shopper import Shopper
from .market.merchant import Behaviour, build_market
from .rail import Authorisation, Rail
from .uap.delegation import Agent, Device, Household, Principal, Revocation
from .uap.intent import Intent, Money, Quantity, Substitution, Unit
from .uap.ledger import Ledger
from .uap.mandate import Keypair, intent_mandate
from .uap.drift import DriftReport


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

def _q(a: str, u: Unit) -> Quantity:
    return Quantity(Decimal(a), u)


ATTA = dict(
    item="atta",
    max_quantity=_q("1", Unit.KG),
    max_total=100,
    max_unit_price_per=(56, Unit.KG),
    allowed_merchants=("blinkit", "instamart", "bigbasket"),
    substitution=Substitution.NONE,
    max_price_drift_bps=0,
)


@dataclass
class World:
    household: Household
    dad: Principal
    mum: Principal
    teen: Principal
    fridge: Device
    agent: Agent
    shopper: Shopper
    rail: Rail
    ledger: Ledger


def build_world(injection_aware: bool = False, rogue: bool = False) -> World:
    dad = Principal("Dad", Keypair("Dad"))
    mum = Principal("Mum", Keypair("Mum"))
    teen = Principal("Teen", Keypair("Teen"))

    fridge = Device("fridge-01", Keypair("fridge-01"), shared=True)

    agent_key = Keypair("agent:fridge-restock")
    agent = Agent("fridge-restock", agent_key, fridge, purpose="grocery-restock")

    # Dad: broad but not unlimited. Mum: broad. Teen: dairy only.
    agent.grant(dad, Money.rupees(4_000), categories=frozenset({"flour", "grain", "dairy"}))
    agent.grant(mum, Money.rupees(4_000))
    agent.grant(teen, Money.rupees(500), categories=frozenset({"dairy"}))

    household = Household("Anand", [dad, mum, teen], [fridge], [agent])

    ledger = Ledger()
    for p in (dad, mum, teen):
        ledger.open_account(p.name, p.account_balance)

    return World(
        household=household, dad=dad, mum=mum, teen=teen, fridge=fridge, agent=agent,
        shopper=Shopper("fridge-restock", agent_key,
                        injection_aware=injection_aware, ignore_allowlist=rogue),
        rail=Rail(Keypair("npci-uap"), ledger), ledger=ledger,
    )


# --------------------------------------------------------------------------
# Result plumbing
# --------------------------------------------------------------------------

@dataclass
class Result:
    authorised: bool
    reason: str
    drift: DriftReport | None
    auth: Authorisation | None
    agent_trace: list[str] = field(default_factory=list)
    merchant_log: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class Scenario:
    key: str
    family: str
    title: str
    premise: str
    expect_authorised: bool
    expect_violation: str | None
    run: Callable[[], Result]


def _shop(world: World, market, intent_kwargs: dict, principal: Principal) -> Result:
    intent = Intent.build(**intent_kwargs)
    im = intent_mandate(intent, principal.key, world.agent.agent_id, nonce="n1")

    sel = world.shopper.select(intent, market)
    if sel is None:
        return Result(False, "agent found nothing", None, None,
                      world.shopper.trace, _logs(market))

    cart = world.shopper.build_cart(sel, im.id)
    auth = world.rail.authorise(intent, im, cart, principal.key, world.agent)
    return Result(auth.approved, auth.reason, auth.drift, auth,
                  world.shopper.trace, _logs(market))


def _logs(market) -> list[str]:
    out = []
    for s in market.values():
        out.extend(s.log)
    return out


# --------------------------------------------------------------------------
# Adversarial scenarios
# --------------------------------------------------------------------------

def s_honest():
    w = build_world()
    m = build_market()
    r = _shop(w, m, ATTA, w.dad)
    r.note = "cheapest honest offer is instamart/atta:fortune-1kg at Rs 54.00/kg"
    return r


def s_unit_confusion():
    w = build_world()
    m = build_market({"instamart": {Behaviour.UNIT_CONFUSION}})
    r = _shop(w, m, ATTA, w.dad)
    r.note = "a 500g pack advertised at its pack price as though it were per-kg"
    return r


def s_quote_drift():
    w = build_world()
    m = build_market({"blinkit": {Behaviour.QUOTE_DRIFT}})
    r = _shop(w, m, ATTA, w.dad)
    r.note = "quoted 15% below the price actually charged at checkout"
    return r


def s_false_stock():
    w = build_world()
    m = build_market({"instamart": {Behaviour.FALSE_STOCK}})
    r = _shop(w, m, ATTA, w.dad)
    r.note = "cheapest SKU hidden, pushing the agent onto a 5kg pack"
    return r


def s_injection_naive():
    w = build_world(injection_aware=False)
    m = build_market({"blinkit": {Behaviour.INJECTION}})
    r = _shop(w, m, ATTA, w.dad)
    r.note = "agent follows an instruction embedded in a product description"
    return r


def s_injection_defended():
    w = build_world(injection_aware=True)
    m = build_market({"blinkit": {Behaviour.INJECTION}})
    r = _shop(w, m, ATTA, w.dad)
    r.note = "same attack, agent recognises and ignores the injected text"
    return r


def s_substitution():
    w = build_world()
    m = build_market({"instamart": {Behaviour.SUBSTITUTION}})
    r = _shop(w, m, ATTA, w.dad)
    r.note = "atta ordered, maida fulfilled, no substitution authorised"
    return r


def s_arithmetic():
    w = build_world()
    m = build_market({"instamart": {Behaviour.ARITHMETIC}})
    r = _shop(w, m, ATTA, w.dad)
    r.note = "line total inflated 20% while the declared unit price is left innocent"
    return r


def s_oversupply():
    w = build_world()
    m = build_market({"instamart": {Behaviour.OVERSUPPLY}})
    r = _shop(w, m, ATTA, w.dad)
    r.note = "2kg supplied against an order for 1kg"
    return r


def s_rogue_agent():
    w = build_world(rogue=True)
    m = build_market({"instamart": {Behaviour.FALSE_STOCK}})
    kw = dict(ATTA, allowed_merchants=("blinkit", "instamart"))
    r = _shop(w, m, kw, w.dad)
    r.note = "agent shops at bigbasket, which the intent never authorised"
    return r


def s_tampered_intent():
    w = build_world()
    m = build_market()
    intent = Intent.build(**ATTA)
    im = intent_mandate(intent, w.dad.key, w.agent.agent_id, nonce="n1")

    # raise the ceiling after signing, without the principal's key
    forged = im.tamper(constraints=dict(intent.to_dict(), max_total_paise=999_00))

    sel = w.shopper.select(intent, m)
    cart = w.shopper.build_cart(sel, forged.id)
    auth = w.rail.authorise(intent, forged, cart, w.dad.key, w.agent)
    return Result(auth.approved, auth.reason, auth.drift, auth,
                  w.shopper.trace, _logs(m),
                  note="intent payload edited after signing")


# --------------------------------------------------------------------------
# Delegation scenarios -- the shape UPI Circle cannot express
# --------------------------------------------------------------------------

def s_multi_principal_scoped():
    w = build_world()
    m = build_market()
    kw = dict(ATTA, item="milk", max_quantity=_q("1", Unit.L),
              max_unit_price_per=(70, Unit.L), max_total=100,
              allowed_merchants=("blinkit", "instamart"))
    r = _shop(w, m, kw, w.dad)
    r.note = ("three principals fund one agent; dairy is in Teen's scoped grant, "
              "so the narrower consent is consumed first")
    return r


def s_uncovered_category():
    w = build_world()
    m = build_market()
    # Mum's grant is unrestricted, so it covers alcohol and every other category.
    # One unrestricted grant defeats category scoping for the entire household --
    # revoke it and the scoping the others chose actually binds.
    w.household.revoke_all_from(w.mum)
    kw = dict(ATTA, item="beer", max_quantity=_q("650", Unit.ML),
              max_unit_price_per=(300, Unit.L), max_total=200,
              allowed_merchants=("bigbasket",))
    r = _shop(w, m, kw, w.dad)
    r.note = ("Dad scoped to flour/grain/dairy, Teen to dairy, Mum's unrestricted "
              "grant revoked -- nothing covers 'alcohol'")
    return r


def s_revocation_partial():
    w = build_world()
    m = build_market()
    n = w.household.revoke_all_from(w.mum)
    r = _shop(w, m, ATTA, w.dad)
    r.note = f"Mum revoked ({n} delegation(s)); Dad's grant is untouched"
    return r


def s_device_reset():
    w = build_world()
    m = build_market()
    w.fridge.factory_reset()
    r = _shop(w, m, ATTA, w.dad)
    r.note = "fridge sold and factory-reset; every delegation bound to it dies"
    return r


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [
    Scenario("honest", "adversarial", "Honest market",
             "all three merchants report truthfully",
             True, None, s_honest),
    Scenario("unit-confusion", "adversarial", "Unit confusion",
             "pack price presented as a per-kg price",
             False, "unit_price", s_unit_confusion),
    Scenario("quote-drift", "adversarial", "Quote drift",
             "discovery price lower than the price charged",
             False, "quote_drift", s_quote_drift),
    Scenario("false-stock", "adversarial", "False out-of-stock",
             "cheap SKU hidden to force a larger pack",
             False, "quantity", s_false_stock),
    Scenario("injection", "adversarial", "Listing injection, naive agent",
             "instructions embedded in merchant-supplied text",
             False, "quantity", s_injection_naive),
    Scenario("injection-defended", "adversarial", "Listing injection, defended agent",
             "same payload, agent ignores it",
             True, None, s_injection_defended),
    Scenario("substitution", "adversarial", "Silent substitution",
             "different item shipped after the order is placed",
             False, "substitution", s_substitution),
    Scenario("arithmetic", "adversarial", "Line-total arithmetic",
             "total inflated, declared unit price left innocent",
             False, "arithmetic", s_arithmetic),
    Scenario("oversupply", "adversarial", "Oversupply",
             "more delivered than ordered",
             False, "quantity", s_oversupply),
    Scenario("rogue-agent", "adversarial", "Agent leaves the allow-list",
             "compromised or buggy agent shops off-list",
             False, "merchant", s_rogue_agent),
    Scenario("tampered-intent", "adversarial", "Tampered intent mandate",
             "signed intent edited after the fact",
             False, "signature", s_tampered_intent),

    Scenario("multi-principal", "delegation", "Multi-principal household",
             "three principals fund one shared agent",
             True, None, s_multi_principal_scoped),
    Scenario("uncovered-category", "delegation", "Category outside every grant",
             "an unrestricted grant is a hole in everyone else's scoping",
             False, None, s_uncovered_category),
    Scenario("revocation", "delegation", "One principal revokes",
             "Mum withdraws; the rest of the household is unaffected",
             True, None, s_revocation_partial),
    Scenario("device-reset", "delegation", "Device factory reset",
             "shared appliance resold",
             False, None, s_device_reset),
]
