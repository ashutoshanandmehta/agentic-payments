# Corpus Corrections — 7 August 2026, updated 24 August 2026

Five claims in the existing documents are contradicted or unsupported by sources checked on
7 Aug 2026. Three of them are load-bearing. Full sourcing in
`agentic-payments-fact-base-2026-08.md`.

**C6 and C7 were added on 24 Aug 2026** after reading the AP2 specification directly. C6 is the
most consequential entry in this file: part of the stated contribution is already specified by
AP2 v0.2. C7 is where the contribution moves to, and it is a stronger position than the one it
replaces.

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

## C6 — "AP2 defines Intent, Cart and Payment Mandates" ❌ OUT OF DATE, and it scoops part of the contribution

*Added 24 August 2026. Checked against the AP2 specification directly.*

**Appears in:** `docs/project-brief-crypto.tex` §III-A, and the PDF sent to Prof. Vadapalli.

**Current wording:** *"AP2 defines three signed artifacts as W3C Verifiable Credentials. An
Intent Mandate says what the user asked for. A Cart Mandate says what the agent selected. A
Payment Mandate authorises the movement."*

**What the source says:** v0.2 defines **two** mandate types — a **Checkout Mandate** and a
**Payment Mandate** — each existing in an **Open** and a **Closed** stage. The three-artifact
naming is v0.1. (The Python SDK still ships the v0.1 classes `IntentMandate`, `CartMandate`,
`PaymentMandate`, so code and documentation currently disagree.)

**The part that matters more than the naming.** v0.2 already specifies the mechanism the brief
presents as the contribution:

- Open mandates are user-signed constraints created **before a cart exists**, for autonomous
  execution — the "authorise before the merchant is known" case.
- *"The Payment Mandate is bound to a particular Checkout using the cryptographic hash of the
  Checkout JWT."* That is Check A.
- The merchant *"verifies that the constraints in the open Checkout Mandate have been met."*
  That is Check B.

**Consequence:** "bind a payment to an agreed order" is no longer a novel mechanism. It is
specified, open source under Apache 2.0, and backed by Google and the FIDO Alliance. The
contribution has to move. See C7 for where it moves to.

**Source:** https://ap2-protocol.org/ap2/specification/ and `/ap2/flows/`, read 24 Aug 2026.
Google maintains AP2 and has a commercial interest in it.

---

## C7 — AP2's autonomous authority carries no spending limit ✅ NEW, and it is the opening

*Added 24 August 2026.*

**Status:** `PRIMARY`. Checked in both the v0.1 SDK source and the v0.2 specification.

`IntentMandate` in `code/sdk/python/ap2/models/mandate.py` has exactly six fields:
`user_cart_confirmation_required`, `natural_language_description`, `merchants`, `skus`,
`requires_refundability`, `intent_expiry`. **No amount, no cap, no budget, no currency.**

The v0.2 open Checkout Mandate carries `vct`, `constraints`, `cnf`, `iat`, `exp`, with
constraint types `checkout.allowed_merchants` and `checkout.line_items`. It constrains *who*
and *what*. It does not constrain *how much*.

**Why this is the opening.** `tests/test_consent.py` already demonstrates that a self-consistent
inflated cart passes every signing arrangement, and that what refuses it is a per-transaction
ceiling close to the real basket size. AP2's autonomous flow has the **shopping agent** sign the
closed mandate — *"the Shopping Agent MAY now sign it using its Agent Key instead of getting
approval on a Trusted Surface"* — which is precisely the arrangement the simulator shows does
not bound the loss.

So the finding restates against a named, live, industry-backed protocol instead of a
hypothetical: **constraint tightness bounds the loss; signature provenance does not, and AP2's
autonomous authority has no monetary constraint to tighten.**

**Caveat before this goes in a paper:** `constraints` is an extensible array. Someone could
define a budget constraint type tomorrow, and there may be constraint types not listed on the
page read. Re-check before submission, and phrase it as "no budget constraint type is defined
among those documented", not "AP2 cannot express a budget".

**Two further things AP2 does not answer, both still open:**

1. **No enforcement party on UPI.** AP2 puts the check at the Merchant Payment Processor. UPI
   has no such role in the path and the switch carries no such field. Where does the check run
   on a rail with nobody to run it?
2. **No UPI binding at all.** AP2 says nothing about Reserve Pay or UPI Circle.

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
| "Binding a payment to an agreed order is the contribution" | Novel mechanism | Specified by AP2 v0.2. Not novel — see C6 |
| "Who signs the cart matters less than the ceiling" | A finding about signatures in general | Evidence against AP2's autonomous mode specifically, which has no ceiling field at all — see C7 |
