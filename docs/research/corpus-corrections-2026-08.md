# Corpus Corrections — 7 August 2026

Five claims in the existing documents are contradicted or unsupported by sources checked on
7 Aug 2026. Three of them are load-bearing. Full sourcing in
`agentic-payments-fact-base-2026-08.md`.

Read this before presenting any deck or submitting the thesis proposal.

---

## C1 — "The customer has no self-service revoke on Reserve Pay" ❌ WRONG

**Appears in:** `warrant-interlock-product-document.md` §5 ("Missing safeguard 2"), §11 (the
consumer-dashboard idea), §13, and repeated at line 503; `thesis-problem-definition.md` A5.

**Current wording:** *"On Reserve Pay, the customer 'will not find revoke option on the TPAP'
and must contact the merchant to get the mandate revoked."*

**What the sources say:** Cashfree's developer documentation states plainly that *"customers
can cancel the mandate directly from their UPI app using the cancellation option."* Summaries
of OC 228 state that UPI apps **must** provide easy access to revoke blocks and display a
consolidated view of all active blocks.

**Replacement wording:**
> Reserve Pay requires UPI apps to offer block revocation and a consolidated view of active
> blocks. Whether that obligation is actually implemented across TPAPs is an open empirical
> question — and for some merchant categories the block may be issued as irrevocable. The
> safeguard exists in the specification; its presence in production has not been verified.

**Consequence:** the "user cannot stop a misbehaving agent" argument must be softened from a
design gap to an implementation-and-latency gap. The consumer-dashboard product idea in §11
loses most of its rationale.

---

## C2 — "One active mandate per customer" ❌ WRONG

**Appears in:** `warrant-interlock-product-document.md:339`, §12.1 (pricing), §14 challenge 1
(market-size pessimism); `agentic-payments-product-research-and-decks.md` §1.4.

**What the sources say:** the constraint is **one block per merchant per customer**. Multiple
concurrent blocks across *different* merchants are permitted, and the required
consolidated-view UI presupposes them.

**Consequence — this one cuts in your favour and against you at once:**
- **For:** the per-merchant, per-category mandate architecture is implementable on today's rail.
  A user really can hold Blinkit + Zepto + Swiggy + IRCTC blocks simultaneously.
- **Against:** the market is larger than §12.1 assumed, which weakens the "too early, no volume"
  framing — but also means more mandate surface for someone else to build controls on.

**Replacement wording:**
> Reserve Pay permits one active block per merchant per customer, capped at ₹10,000 for up to
> 90 days. A customer may hold concurrent blocks across multiple merchants; UPI apps are
> required to show all of them in one view.

---

## C3 — "Pre-debit notification is not required on Reserve Pay" ⚠️ UNVERIFIED

**Appears in:** `warrant-interlock-product-document.md` §5, §9.6 — where it is described as
*"the strongest single argument this product has"*; `thesis-problem-definition.md` A5.

**Status:** no circular text found stating this. Every source that implies it does so by
*contrast* with Autopay's 24-hour PDN requirement, which is not the same as a stated exemption.
Separately, issuer banks **are** required to notify on block creation, modification, **debit**,
revoke and expiry — so a debit notification does exist; it is simply not a *pre*-debit veto
window.

**Action:** read OC 228 §-by-§ before this claim is used in a deck, a paper, or the NPCI
consultation response. If it fails, the "registration-time authentication and no debit-time
control at all" argument fails with it, and the honest position becomes *"the notification is
post-hoc, so the human learns after the money moved."* That is a weaker but still real claim.

---

## C4 — "Agent payments are not on RBI's exemption list" ⚠️ CONTESTED — highest impact

**Appears in:** `thesis-problem-definition.md` §P1, where the argument runs: agent debits cannot
produce a fresh factor → they are not exempt → every one is non-compliant → under Section 9 the
bank compensates in full.

**What the sources say:** the exemption list in the RBI (Authentication Mechanisms for Digital
Payment Transactions) Directions, 2025 **includes "recurring transactions under the e-mandate
framework."** The stated rationale is that initial authentication established trust and such
transactions rely on tokenisation or pre-authorised mandates.

**The crux:** whether UPI Reserve Pay sits *inside* "the e-mandate framework" for the purposes
of that exemption. If it does, agent debits against a Reserve Pay block are exempt and the
compliance argument largely dissolves. If it does not, the original argument stands.

**Replacement wording:**
> The Directions exempt recurring transactions under the e-mandate framework. Whether Reserve
> Pay-based agent debits fall inside that exemption is unresolved and, so far as we can find,
> has not been addressed publicly by RBI or NPCI. The question is material: it determines
> whether agent-initiated UPI payments are already compliant, or systematically non-compliant
> with full issuer liability under Section 9.

**This is now a better research question than a settled premise** — and it is exactly the kind
of question the UAP consultation exists to answer. Ask it there.

---

## C5 — "Flipkart has an MCP implementation" ❌ UNSUPPORTED

**Appears in:** not yet in the corpus — it surfaced during this research round via a single
aggregator and did not survive a targeted search. Recorded here so it does not enter the corpus.

Confirmed Indian MCP/agentic commerce: **Swiggy** (Food, Instamart, Dineout — but
**cash-on-delivery only**, and gated behind ChatGPT developer mode) and **BigBasket** (embedded
UPI via Razorpay on Reserve Pay, with a single human confirmation step). Flipkart is a named
UCP partner, which is not the same thing.

---

## What survives unchanged

Worth stating, because most of the corpus holds:

- ₹10,000 / 90-day ceiling — confirmed
- No UPI PIN per debit; one strong authentication event at block creation — confirmed
- UAP still unlaunched, no RBI approval, anonymous sourcing — confirmed, and the standards
  window is genuinely still open
- UPI Circle's person-with-a-PIN assumption and the strain of extending it to agents — holds
- The instruction-origin gap itself — holds, and is now independently corroborated by
  `arXiv:2604.15367`, which names it as open work. **But that also means the observation is no
  longer novel; only a mechanism would be.**
- The dispute/UDIR reason-code gap — holds, and industry participants in the UAP consultation
  are reportedly raising it themselves

## Net effect on the two arguments

| Argument | Before | After |
|---|---|---|
| "Reserve Pay removed the safeguards" | Three missing safeguards | One confirmed weaker (post-debit not pre-debit notification), one wrong (revoke exists in spec), one unverified |
| "Agent debits are non-compliant, banks eat the loss" | Asserted | Genuinely open — hinges on the e-mandate exemption reading |
| "Instruction origin is unverified after mandate creation" | Novel observation | Still true, now corroborated in the literature — needs a mechanism to be a contribution |
| "The rail can't support per-category mandates" | Implied by one-mandate reading | False. It can, today |
