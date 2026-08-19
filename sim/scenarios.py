"""
Scenarios.

Each one says what it expects before it runs. If the system does something else, the
harness reports it as a finding rather than quietly passing.

Three groups:

  TAMPERING    something changed between the cart being agreed and the money moving
  AUTHORITY    the agent went outside what the human allowed
  DELEGATION   several people fund one agent -- whose money pays, and what survives
               a revocation
  CART SIGNING an experiment on the open question: who should sign the cart?
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .rail import Outcome, Rail
from .uap.authority import Money, PaymentAuthority
from .uap.cart import Cart, PaymentRequest
from .uap.check import CheckResult
from .uap.delegation import Agent, Device, Household, Principal
from .uap.mandate import (
    CartSigner,
    Keypair,
    authority_record,
    cart_record,
    request_record,
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@dataclass
class World:
    household: Household
    dad: Principal
    mum: Principal
    teen: Principal
    fridge: Device
    agent: Agent
    rail: Rail
    shops: dict[str, Keypair]


def build_world(cart_signer: CartSigner = CartSigner.AGENT) -> World:
    dad = Principal("Dad", Keypair("Dad"))
    mum = Principal("Mum", Keypair("Mum"))
    teen = Principal("Teen", Keypair("Teen"))

    fridge = Device("fridge-01", Keypair("fridge-01"), shared=True)
    agent = Agent("fridge-restock", Keypair("agent:fridge-restock"), fridge)

    # Dad: groceries and transport. Mum: anything. Teen: dairy only, small budget.
    agent.grant(dad, Money.rupees(4_000), categories=frozenset({"grocery", "transport"}))
    agent.grant(mum, Money.rupees(4_000))
    agent.grant(teen, Money.rupees(500), categories=frozenset({"dairy"}))

    return World(
        household=Household("Anand", [dad, mum, teen], [fridge], [agent]),
        dad=dad, mum=mum, teen=teen, fridge=fridge, agent=agent,
        rail=Rail(Keypair("npci-uap"), cart_signer=cart_signer),
        shops={n: Keypair(n) for n in ("blinkit", "instamart", "bigbasket")},
    )


#: the standard authority: up to Rs 800 a payment, Rs 2,000 total, three shops,
#: groceries only, at most 2 payments, valid for ticks 0-100
def standard_authority(**over) -> PaymentAuthority:
    base = dict(
        max_per_payment=800, max_total=2_000,
        allowed_merchants=("blinkit", "instamart", "bigbasket"),
        allowed_categories=("grocery",),
        max_payments=2, valid_from=0, valid_until=100,
    )
    base.update(over)
    return PaymentAuthority.build(**base)


def standard_cart(**over) -> Cart:
    base = dict(
        cart_id="cart-1", merchant="instamart", category="grocery",
        lines=[("Fortune Atta 1kg", 54), ("Amul Milk 1L", 64)],
        agreed_at=10,
    )
    base.update(over)
    return Cart.build(**base)


# --------------------------------------------------------------------------
# Plumbing
# --------------------------------------------------------------------------

@dataclass
class Result:
    approved: bool
    reason: str
    result: CheckResult | None
    outcome: Outcome | None
    note: str = ""


@dataclass
class Scenario:
    key: str
    family: str
    title: str
    premise: str
    expect_approved: bool
    expect_violation: str | None
    run: Callable[[], Result]


def _pay(w: World, authority: PaymentAuthority, cart: Cart,
         request: PaymentRequest, principal: Principal,
         tamper_authority: dict | None = None) -> Result:
    """Sign the three records and put them to the rail."""
    arec = authority_record(authority, principal.key, w.agent.agent_id)
    if tamper_authority is not None:
        arec = arec.tamper(**tamper_authority)

    crec = cart_record(cart, w.rail.cart_signer, w.agent.key, w.shops[cart.merchant])
    rrec = request_record(request, arec.id, w.agent.key)

    out = w.rail.authorise(
        authority=authority, authority_rec=arec, cart_rec=crec, request_rec=rrec,
        principal_key=principal.key, agent=w.agent,
        merchant_key=w.shops[request.merchant], now=request.requested_at,
    )
    return Result(out.approved, out.reason, out.result, out)


def _req(cart: Cart, at: int = 20, amount: Money | None = None,
         merchant: str | None = None, nonce: str = "1") -> PaymentRequest:
    return PaymentRequest(
        cart_ref=cart.cart_id,
        merchant=merchant or cart.merchant,
        amount=amount or cart.total,
        requested_at=at, nonce=nonce,
    )


# --------------------------------------------------------------------------
# TAMPERING -- something changed between cart and payment
# --------------------------------------------------------------------------

def s_clean():
    w = build_world()
    c = standard_cart()
    r = _pay(w, standard_authority(), c, _req(c), w.dad)
    r.note = "Rs 118 cart at instamart, inside every limit"
    return r


def s_price_drift():
    w = build_world()
    c = standard_cart()
    # cart agreed at Rs 118; surge pricing pushes the debit to Rs 162
    r = _pay(w, standard_authority(), c, _req(c, amount=Money.rupees(162)), w.dad)
    r.note = "human agreed Rs 118; the debit is Rs 162, still under the Rs 800 limit"
    return r


def s_payee_swap():
    w = build_world()
    c = standard_cart()
    r = _pay(w, standard_authority(), c, _req(c, merchant="blinkit"), w.dad)
    r.note = "cart agreed with instamart, money routed to blinkit -- both are approved shops"
    return r


def s_double_debit():
    w = build_world()
    c = standard_cart()
    a = standard_authority()
    _pay(w, a, c, _req(c, at=20, nonce="n1"), w.dad)      # first payment settles
    r = _pay(w, a, c, _req(c, at=21, nonce="n1"), w.dad)   # agent retries after timeout
    r.note = "agent timed out and retried; the same payment arrives twice"
    return r


def s_cart_arithmetic():
    w = build_world()
    c = standard_cart(total=300)   # lines add to 118, total claims 300
    r = _pay(w, standard_authority(), c, _req(c), w.dad)
    r.note = "cart lines add to Rs 118 but the total says Rs 300"
    return r


def s_forged_authority():
    w = build_world()
    c = standard_cart()
    a = standard_authority()
    forged = {"terms": dict(a.to_dict(), max_per_payment_paise=9_999_00)}
    r = _pay(w, a, c, _req(c), w.dad, tamper_authority=forged)
    r.note = "limit raised after the human signed, without the human's key"
    return r


# --------------------------------------------------------------------------
# AUTHORITY -- the agent went outside what was allowed
# --------------------------------------------------------------------------

def s_wrong_shop():
    w = build_world()
    c = standard_cart(merchant="bigbasket")
    a = standard_authority(allowed_merchants=("blinkit", "instamart"))
    r = _pay(w, a, c, _req(c), w.dad)
    r.note = "bigbasket was never on the approved list"
    return r


def s_wrong_category():
    w = build_world()
    c = standard_cart(category="alcohol", lines=[("Lager 650ml", 160)])
    r = _pay(w, standard_authority(), c, _req(c), w.dad)
    r.note = "authority covers groceries; the cart is alcohol"
    return r


def s_over_per_payment():
    w = build_world()
    c = standard_cart(lines=[("Bulk order", 1_400)])
    r = _pay(w, standard_authority(), c, _req(c), w.dad)
    r.note = "Rs 1,400 against a Rs 800 per-payment limit"
    return r


def s_over_budget():
    w = build_world()
    a = standard_authority(max_payments=5)
    c1 = standard_cart(cart_id="c1", lines=[("Weekly shop", 750)])
    c2 = standard_cart(cart_id="c2", lines=[("Weekly shop", 750)])
    c3 = standard_cart(cart_id="c3", lines=[("Weekly shop", 750)])
    _pay(w, a, c1, _req(c1, at=20, nonce="a"), w.dad)
    _pay(w, a, c2, _req(c2, at=30, nonce="b"), w.dad)
    r = _pay(w, a, c3, _req(c3, at=40, nonce="c"), w.dad)
    r.note = "three Rs 750 payments against a Rs 2,000 total budget"
    return r


def s_too_many_payments():
    w = build_world()
    a = standard_authority()   # max_payments = 2
    for i, t in enumerate((20, 30), start=1):
        c = standard_cart(cart_id=f"c{i}")
        _pay(w, a, c, _req(c, at=t, nonce=f"n{i}"), w.dad)
    c3 = standard_cart(cart_id="c3")
    r = _pay(w, a, c3, _req(c3, at=40, nonce="n3"), w.dad)
    r.note = "third payment against an authority good for two"
    return r


def s_expired():
    w = build_world()
    c = standard_cart(agreed_at=150)
    r = _pay(w, standard_authority(), c, _req(c, at=160), w.dad)
    r.note = "authority ran out at tick 100; the payment arrives at tick 160"
    return r


# --------------------------------------------------------------------------
# DELEGATION -- several people fund one agent
# --------------------------------------------------------------------------

def s_multi_principal():
    w = build_world()
    c = standard_cart(category="dairy", lines=[("Amul Milk 1L", 64)])
    a = standard_authority(allowed_categories=("grocery", "dairy"))
    r = _pay(w, a, c, _req(c), w.dad)
    r.note = ("three people fund one fridge; dairy sits in Teen's narrow grant, "
              "so the narrower consent is used first")
    return r


def s_nobody_covers():
    w = build_world()
    w.household.revoke_all_from(w.mum)     # Mum's grant was the unrestricted one
    c = standard_cart(category="alcohol", lines=[("Lager 650ml", 160)])
    a = standard_authority(allowed_categories=("grocery", "alcohol"))
    r = _pay(w, a, c, _req(c), w.dad)
    r.note = ("Dad covers grocery/transport, Teen dairy, Mum's unrestricted grant "
              "revoked -- so nothing covers alcohol")
    return r


def s_partial_revocation():
    w = build_world()
    n = w.household.revoke_all_from(w.mum)
    c = standard_cart()
    r = _pay(w, standard_authority(), c, _req(c), w.dad)
    r.note = f"Mum revoked {n} grant; Dad's is untouched"
    return r


def s_revocation_race():
    w = build_world()
    c = standard_cart()
    a = standard_authority()
    # every principal pulls out at tick 15, after the cart, before the payment
    for p in (w.dad, w.mum, w.teen):
        w.household.revoke_all_from(p)
    r = _pay(w, a, c, _req(c, at=20), w.dad)
    r.note = "cart agreed at tick 10, everyone revokes at 15, payment arrives at 20"
    return r


def s_device_reset():
    w = build_world()
    w.fridge.factory_reset()
    c = standard_cart()
    r = _pay(w, standard_authority(), c, _req(c), w.dad)
    r.note = "fridge sold and wiped; every grant tied to it dies with it"
    return r


# --------------------------------------------------------------------------
# CART SIGNING -- the open question, run as an experiment
# --------------------------------------------------------------------------

def _consistent_lie(signer: CartSigner, max_per_payment: int = 800) -> Result:
    """
    The cart says Rs 600 and its lines add to Rs 600. Nothing is inconsistent.

    The human only ever agreed to a Rs 118 basket, but no record of that survives --
    the cart IS the record. Arithmetic cannot help here, so this isolates what the
    signature alone is worth.
    """
    w = build_world(cart_signer=signer)
    c = standard_cart(lines=[("Fortune Atta 1kg", 300), ("Amul Milk 1L", 300)])
    a = standard_authority(max_per_payment=max_per_payment)
    return _pay(w, a, c, _req(c), w.dad)


def s_sign_agent_only():
    r = _consistent_lie(CartSigner.AGENT)
    r.note = "agent signs a self-consistent Rs 600 cart. signature valid, arithmetic fine"
    return r


def s_sign_merchant_only():
    r = _consistent_lie(CartSigner.MERCHANT)
    r.note = "shop signs the same Rs 600 cart. signature valid, arithmetic fine"
    return r


def s_sign_both():
    r = _consistent_lie(CartSigner.BOTH)
    r.note = "both sign it. still nothing to compare Rs 600 against"
    return r


def s_tight_authority():
    """The thing that actually stops it: a limit close to the expected basket."""
    r = _consistent_lie(CartSigner.BOTH, max_per_payment=150)
    r.note = "same Rs 600 cart, but the authority allows only Rs 150 a payment"
    return r


def s_sign_both_absent():
    """The realistic cost of requiring two signatures: the shop does not participate."""
    w = build_world(cart_signer=CartSigner.BOTH)
    c = standard_cart()
    a = standard_authority()
    arec = authority_record(a, w.dad.key, w.agent.agent_id)
    crec = cart_record(c, CartSigner.AGENT, w.agent.key, w.shops[c.merchant])
    rrec = request_record(_req(c), arec.id, w.agent.key)
    out = w.rail.authorise(
        authority=a, authority_rec=arec, cart_rec=crec, request_rec=rrec,
        principal_key=w.dad.key, agent=w.agent,
        merchant_key=w.shops[c.merchant], now=20,
    )
    return Result(out.approved, out.reason, out.result, out,
                  note="BOTH required, shop never signed -- every payment stops")


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [
    Scenario("clean", "tampering", "Nothing wrong",
             "a normal payment inside every limit", True, None, s_clean),
    Scenario("price-drift", "tampering", "Price changed after agreement",
             "debit is higher than the cart the human saw", False, "amount_changed", s_price_drift),
    Scenario("payee-swap", "tampering", "Money sent to a different shop",
             "cart says instamart, payment says blinkit", False, "payee_changed", s_payee_swap),
    Scenario("double-debit", "tampering", "Same payment twice",
             "agent retried after a timeout", False, "replay", s_double_debit),
    Scenario("cart-arithmetic", "tampering", "Cart total does not match its lines",
             "lines add to Rs 118, total claims Rs 300", False, "cart_arithmetic", s_cart_arithmetic),
    Scenario("forged-authority", "tampering", "Authority edited after signing",
             "limit raised without the human's key", False, "signature", s_forged_authority),

    Scenario("wrong-shop", "authority", "Shop not on the list",
             "paying a shop the human never approved", False, "merchant", s_wrong_shop),
    Scenario("wrong-category", "authority", "Category not allowed",
             "alcohol against a grocery authority", False, "category", s_wrong_category),
    Scenario("over-per-payment", "authority", "Single payment too large",
             "Rs 1,400 against a Rs 800 limit", False, "per_payment", s_over_per_payment),
    Scenario("over-budget", "authority", "Total budget exhausted",
             "three Rs 750 payments against Rs 2,000", False, "budget", s_over_budget),
    Scenario("too-many-payments", "authority", "Used more times than allowed",
             "third payment on a two-payment authority", False, "count", s_too_many_payments),
    Scenario("expired", "authority", "Authority expired",
             "payment arrives after the validity window", False, "window", s_expired),

    Scenario("multi-principal", "delegation", "Three people, one fridge",
             "whose money pays for the milk", True, None, s_multi_principal),
    Scenario("nobody-covers", "delegation", "No grant covers this category",
             "an unrestricted grant is a hole in everyone else's limits", False, None, s_nobody_covers),
    Scenario("partial-revocation", "delegation", "One person pulls out",
             "Mum revokes, Dad's grant survives", True, None, s_partial_revocation),
    Scenario("revocation-race", "delegation", "Revoked while a payment is in flight",
             "cart at 10, revoke at 15, payment at 20", False, None, s_revocation_race),
    Scenario("device-reset", "delegation", "Appliance sold and wiped",
             "device reset kills every grant on it", False, None, s_device_reset),

    Scenario("sign-agent", "cart signing", "Agent signs a consistent lie",
             "does the agent's signature stop an inflated cart?", True, None, s_sign_agent_only),
    Scenario("sign-merchant", "cart signing", "Shop signs a consistent lie",
             "does the shop's signature stop it?", True, None, s_sign_merchant_only),
    Scenario("sign-both", "cart signing", "Both sign a consistent lie",
             "does requiring both signatures stop it?", True, None, s_sign_both),
    Scenario("tight-authority", "cart signing", "A tight authority stops it",
             "what actually works: a limit near the expected basket", False, "per_payment", s_tight_authority),
    Scenario("sign-both-absent", "cart signing", "Both required, shop does not sign",
             "the cost of requiring two signatures", False, "signature", s_sign_both_absent),
]
