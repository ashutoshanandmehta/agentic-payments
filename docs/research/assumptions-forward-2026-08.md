# Forward assumptions — delegated agent payments over UPI

**Created:** 2026-08-19
**Companion to:** `corpus-corrections-2026-08.md` (which audits *past* claims) and
`agentic-payments-fact-base-2026-08.md` (which records *verified present* facts).

This file records **forward-looking assumptions** — claims about a future that has not
arrived, which the simulation/protocol work depends on. The discipline is the same as the
corrections file, run in the other direction: name the assumption, date it, state what would
falsify it, and state what survives if it turns out false.

**Review cadence:** quarterly. Next review **2026-11-19**.

---

## Why this file exists

[`../pitch/UAP.md`](../pitch/UAP.md) slide 7 (1 Aug 2026) declined the consumer bet in explicit terms:

> "Consumer agent payments in India need UAP to ship, RBI to approve, and consumers to adopt.
> That's a bet on two futures and we're not taking it."

On **19 Aug 2026** the decision was made to build the consumer/future version anyway — as
**thesis and standards work in simulation**, not as the revenue path. Slide 7's own kicker
supports this split: *"Same primitives become the consumer UAP layer when the rail opens."*

So the split is deliberate:

| Track | Horizon | Success measure |
|---|---|---|
| **Thesis / standards** | Future rail | Publishable contribution; a seat in UAP consultation |
| **Company** (per `UAP.md`) | Present rail | Paid design partners, pricing discovery |

The risk being managed here is not "the assumptions are wrong." It is "the assumptions were
never written down, so nothing was learned when reality diverged."

---

## The assumption stack

### A1 — NPCI's UAP ships, and is extensible by third parties

- **Status:** `UNVERIFIED`. Reported in consultation Jul 2026. No published spec. Requires RBI approval.
- **Falsifier:** UAP ships as a bank-/PSP-only specification with no third-party extension
  surface, or is shelved.
- **If false:** the drift-measurement layer is rail-agnostic. It still works over AP2 mandates,
  card rails, or any protocol producing signed intent artifacts. **Survivable.**

### A2 — RBI permits agent-initiated payment without per-transaction human confirmation

- **Status:** `CONTESTED`. Every confirmed live Indian agentic flow (BigBasket/ChatGPT/Razorpay,
  Swiggy MCP) retains a human confirmation step — recorded in the fact base. RBI's
  Authentication Directions 2025 exempt "recurring transactions under the e-mandate framework",
  which may or may not extend to agent-initiated variable-payee spend.
- **Falsifier:** RBI guidance mandating explicit per-transaction human authentication for
  agent-initiated payments, with no delegated exemption.
- **If false:** **existential.** Delegated payment collapses to a confirmation UI, and drift
  measurement becomes advisory rather than enforcing. The paper survives; the infrastructure
  premise does not.
- **This is the single variable to track.** It resolves earliest and determines everything downstream.

### A3 — UPI gains a primitive for a budget delegated to an agent and spendable across merchants

- **Status:** `PRIMARY` that it does not exist today. Autopay is fixed-payee with mandatory
  24h pre-debit notification; Reserve Pay is one block **per merchant** (verified in
  `corpus-corrections-2026-08.md`). Both bind a payee *before* the agent has compared anything —
  which is precisely what a comparison agent cannot do.
- **Falsifier:** UAP ships retaining payee-binding at mandate creation.
- **If false:** **this is better, not worse.** "Here is a delegation pattern the rail
  structurally cannot express" is a stronger research contribution than "here is a thing that
  works." Do not hope this one resolves in your favour.

### A4 — Agent intent will be expressed in a machine-checkable form, not free natural language

- **Status:** `SECONDARY`. AP2's Intent Mandate is a signed structured artifact; UCP and ACP
  converge on similar. But no standard yet specifies a *constraint language* rich enough for
  "≤1kg, ≤₹60/kg, weekly, sellers ∈ {A,B,C}".
- **Falsifier:** the industry settles on free-text intent with post-hoc LLM adjudication.
- **If false:** drift becomes hard to measure deterministically — **which is the opportunity.**
  The constraint language is then itself the contribution. Do not treat this as a dependency;
  treat it as the thing to build.

### A5 — Agents drift from instruction often enough to warrant measurement

- **Status:** `UNVERIFIED` for accidental drift. `PRIMARY` for adversarial drift as an attack class.
- **Falsifier (accidental):** models become reliable enough that instruction-following error is negligible.
- **Falsifier (adversarial):** none plausible — attacker leverage grows with agent authority.
- **Mitigation, and the central design choice:** **centre adversarial drift, not accidental drift.**
  Accidental drift is a capability gap that model progress closes; building on it means racing
  model progress. Adversarial drift is a security property that *worsens* with autonomy.
  [`../pitch/UAP.md`](../pitch/UAP.md) Appendix B already contains the seed — *"the memo is written by the party under
  suspicion"* — but has not made it the centre.

### A6 — Smart appliances / ambient surfaces become a purchase channel in India

- **Status:** `UNVERIFIED` and weak. Smart-fridge install base is near zero (Family Hub ≈ ₹2L+).
  Blinkit/Instamart/BigBasket have no public ordering API or self-serve partner programme.
- **Falsifier:** irrelevant.
- **Load-bearing:** **no. Decorative.** The trust layer is surface-agnostic.
- **How to apply:** keep the fridge as *narrative only*. Never buy hardware, never build a
  retailer integration for it. Use **ONDC** (open Beckn specs, free staging registry, live RET10
  grocery, 400+ seller apps) as the actual demo surface — it gives real multi-seller price
  comparison without a partnership.

---

## The simulated world (A7-A15)

> **Scope note, 19 Aug 2026.** The project narrowed to *delegated payments only* —
> work starts when the agent tries to pay, with the cart already full. Assumptions
> below that concern product discovery, price comparison or shop selection (most of
> A10 and A11) are now out of scope and are kept only as record. A7, A8, A9, A12,
> A13, A14 and A15 all still apply.


Added **2026-08-19** when `sim/` was built. A1-A6 are bets about how the world
resolves. These are the *world the simulation runs in* -- the state of affairs
assumed true so that delegated agent payment is possible at all. Each is stated so
a reader can disagree with it specifically.

The dividing line that matters: **A7-A13 remove obstacles, A14-A15 create them.**
A simulation built only from obstacle-removing assumptions can produce exactly one
result -- *it works* -- and teaches nothing. A14 and A15 are what make it research.

### A7 - UAP admits non-human delegates

UPI Circle is human-to-human: the secondary authenticates biometrically on a bound
device, holds their own UPI app, and receives a `name@upicircle` handle. A fridge
has no thumb. So "the appliance is a Circle secondary" is not a small extrapolation
of Circle -- it is UAP. The simulation assumes an agent identity chained to a
principal, with scope, expiry and revocation.

**Consequence:** stop saying "delegated payments over UPI Circle". Say "a UAP-shaped
delegation primitive, of which UPI Circle is the nearest existing ancestor". The
difference is not cosmetic -- it is the difference between inheriting a primitive
that cannot express the use case and specifying one that can.

### A8 - Several principals may fund one agent

`PRIMARY` that this is impossible today: a UPI Circle secondary may accept
delegation from **exactly one** primary, and a primary may have at most five
secondaries. Circle is one-to-many; a shared appliance is many-to-one. Under Circle
the family fridge is necessarily one person's fridge.

Implemented in `sim/uap/delegation.py`. Two findings fell out of implementing it,
neither of which was visible before the code existed:

1. **Funding resolution is an unforced policy choice with no good default.**
   Narrowest-scope-first drains the teenager's Rs 500 dairy grant to buy the
   household's milk before touching either parent's Rs 4,000. Unrestricted-first
   makes the least careful member fund everything. A rail shipping multi-principal
   delegation must pick one and defend it. Neither is obviously right.
2. **One unrestricted grant is a hole in everyone else's scoping.** If Dad scopes
   to flour/grain/dairy and Teen to dairy, but Mum grants unrestricted, the
   household's effective policy is Mum's. Category scoping is only as strong as the
   loosest grant in the set. Scenario `uncovered-category` demonstrates it.

### A9 - Device identity is distinct from agent identity

An appliance holds a device identity; the agent chains to both device and
principals. A factory reset or resale revokes every delegation bound to that
device, without touching the same principal's grants to agents on other devices.
Scenario `device-reset`.

### A10 - Quick commerce exposes official agent-facing MCP servers

Catalogue, discovery, cart, checkout. `PRIMARY` that this does not exist today:
what exists is unofficial browser automation (`hereisSwapnil/blinkit-mcp` --
search, cart, checkout, MIT, browser-driven) and read-only Apify scrapers. No
Indian quick-commerce player ships an agent-ordering API.

### A11 - Merchant servers are adversarial by default `<- the load-bearing one`

Not "may be compromised". **Structurally incentivised.** Three merchants each write
text into the agent's context and all three compete for the same single order.
Manipulating selection is the arrangement's own incentive, and every attack in
`sim/market/merchant.py` can be executed from inside a perfectly legitimate server
by choosing what to report.

Attack classes implemented, all of which the mandate chain catches:

| Attack | What the merchant does | Caught by |
|---|---|---|
| `unit_confusion` | 500g pack priced as if per-kg | normalised unit price |
| `quote_drift` | quote 15% under the charge | quoted vs charged in the cart |
| `false_stock` | hide the cheapest SKU per unit | quantity + total ceiling |
| `injection` | instructions in product text | quantity + total ceiling |
| `substitution` | ship maida against an atta order | canonical item key |
| `arithmetic` | inflate line total, leave unit price innocent | recomputed unit price |
| `oversupply` | deliver 2kg against 1kg | normalised quantity |

### A12 - Intent is machine-checkable, not free text

Implemented as `sim/uap/intent.py`. There is deliberately no way to express "prefer"
or "roughly": a preference cannot be checked deterministically, and anything
non-deterministic cannot gate a payment. Every field is a ceiling or an allow-list.

One implementation finding worth recording: **unit-price resolution is itself a
security property.** At paise-per-gram, Rs 54/kg and Rs 59/kg both round to 6
paise/g and every offer in the catalogue ties -- a comparison that cannot separate
real prices cannot detect a manipulated one. Pricing per display unit (kg/l/piece)
fixes it. This is the kind of thing only building finds.

### A13 - Settlement is against a cross-merchant reservation

Funds blocked against the principal's account, captured against whichever merchant
wins. `sim/uap/ledger.py`. This is A3 assumed to resolve favourably; if UAP ships
still binding a payee at mandate creation, that file is the diff.

### A14 - Disputes require the mandate chain as evidence

A chargeback on an agent-initiated payment requires intent + cart + drift report.
Absent all three the merchant wins by default, because nobody can show what was
authorised. `Evidence.complete()` in `sim/uap/mandate.py`.

### A15 - The agent may be compromised

The simulated agent is deliberately naive: it trusts merchant claims, optimises on
displayed unit price, and follows instructions embedded in listings. This is the
design, not a defect. The claim under test is that safety comes from the mandate
chain rather than the agent's judgement -- so the agent must be permitted bad
judgement. An agent that defends itself proves nothing, because a compromised agent
will not defend itself.

Scenarios `injection` and `injection-defended` are the same attack against a naive
and a hardened agent. Both end correctly: the naive agent is stopped by the rail,
not by itself.

---

## What is being claimed as novel

Two things, neither currently in `UAP.md`:

1. **The AP2↔UPI binding is unwritten.** AP2 (Google, Sept 2025, 60+ partners) defines
   Intent/Cart/Payment Mandates as signed W3C Verifiable Credentials and explicitly names UPI as
   a target rail with defined extension points — but it is card/pull-first and ships no UPI
   extension. `SECONDARY`. Juspay is a launch partner and is the obvious prior-art check.

2. **The delta between a signed Intent Mandate and a signed Cart Mandate is decision drift, and
   it is cryptographically measurable.** The payments industry frames agent safety as spend
   caps — *did it stay under the limit*. Drift is the harder question — *did it buy the thing you
   meant*. This connects directly to [`../thesis/thesis-problem-definition.md`](../thesis/thesis-problem-definition.md).

---

## Open items before the next review

- [ ] Verify NPCI circular **UPI/OC No. 228 FY 2025-26** (Reserve Pay enhancements) directly —
      current block limits, duration, merchant scoping. NPCI's site 403s automated fetches.
- [ ] Check whether Juspay has published anything on an AP2 UPI extension (prior-art risk to claim 1).
- [ ] Track A2: any RBI statement on authentication for agent-initiated payments.
- [ ] ONDC staging registry access (form + Slack request).

---

## Prior-art alert: P3P (added 2026-08-20)

**Pine Labs Payments Protocol**, launched 11 June 2026, is the closest existing system to
this thesis and it was not in the corpus before today.

- Built on **UPI ReservePay** (Single Block Multiple Debit) and One Time Mandate --
  the exact rail this work targets. `SECONDARY`
- Uses **HTTP 402** challenge-response, headers `P3P-Credential` and `X-Grantex-Token`.
- **Grantex** is its identity and delegation layer: verifies agent identity, enforces
  pre-approved spend limits, keeps an audit trail. Pine Labs' phrase is "no guardrails,
  no payment."
- Live in production: Gullak (digital gold, agent buys at a target price). Vijay Sales
  in proof of concept.
- Pine Labs acquired Setu in 2022, so this is the same company behind the UPI API layer
  previously considered as a route around a sponsor-bank relationship.

**What this changes.** A1 and A7 are now partly resolved in reality rather than assumed:
a delegation primitive admitting non-human payers exists on UPI today, without waiting
for NPCI's UAP.

**The open question, and it is the important one.** Pine Labs' public docs describe
payment tokens as scoped to "a specific resource, amount and expiry". They do **not**
describe any binding between the payment and an order or cart the user agreed to. If
that absence is real, the order gate remains the contribution. If P3P already binds
payments to an agreed order, **the contribution needs rethinking.**

Status: `UNVERIFIED`. The public docs stop at the quickstart; absence from public docs
is not absence from the protocol.

**How to settle it:** read the P3P TypeScript or Python SDK, or email
`pgintegration@pinelabs.com`. This is now the highest-priority verification item in the
whole project -- higher than OC 228, higher than the Juspay check.

Also relevant, from the same reporting: RBI's Digital Payments E-Mandate Framework 2026
requires Additional Factor of Authentication to *set up* a mandate, and permits recurring
debits up to **Rs 15,000** without AFA once it is set. That figure bears directly on C4
and should be verified against the framework text. `SECONDARY`
