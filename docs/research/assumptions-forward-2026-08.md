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
