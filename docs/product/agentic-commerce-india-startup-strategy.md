# Agentic Commerce in India — Startup Strategy
## Which layer to build, argued from what is actually true in August 2026

**7 August 2026.** Self-contained. Facts trace to `agentic-payments-fact-base-2026-08.md`.
Where this contradicts earlier internal documents, see `corpus-corrections-2026-08.md`.

---

## 0. The verdict up front

Three positions were on the table: a consumer cross-merchant AI shopping agent, a B2B pre-debit
decisioning layer for UPI Reserve Pay, and enterprise agent spend controls.

**Recommendation: build enterprise agent spend control as the company. Run the consumer/UPI work
as research and standards positioning, not as a product.**

This lands near the previously agreed direction, but for **partly different reasons**, and with
one previous argument now removed. The honest summary of what this research round changed:

| | Before | After |
|---|---|---|
| Consumer agent | "Killed — needs UAP + RBI + adoption" | Still the wrong lane, but for **distribution** reasons, not feasibility. The rail supports it *today* |
| Reserve Pay decisioning wedge | The strongest near-term product | **Materially weaker.** Two of its three founding facts were wrong, and there is almost nothing to screen |
| Enterprise agent spend | The pragmatic wedge | **Now the strongest position**, and the only one not exposed to any of the corrections |

---

## 1. Assumption critique — commercial

### 1.1 The approval step contradiction

Nearly every consumer agent design contains a step reading *"obtain final approval from the
user"* between cart assembly and payment. That single line decides whether there is a business.

- **Approval on every purchase** → this is agent-assisted checkout. Existing 2FA works, no
  regulatory collision, no instruction-origin problem — and no new value, because the user still
  makes every decision. You have built a better search interface. **The payment layer is not the
  product and cannot be monetised.**
- **No approval** → all the hard problems return, and you need an answer to every one before a
  bank will let you near a rail.

This is not a detail to design past. **Every confirmed live agentic flow in India today sits on
the first side of that line.** BigBasket's ChatGPT integration presents options and takes a
single human confirmation. Swiggy's MCP integration does not even close the payment loop — AI-tool
orders are **cash on delivery only**.

So today's Indian "agentic commerce" is a conversational storefront, not autonomous purchasing.
Any business model that requires autonomy is priced against a market that does not yet exist.

### 1.2 The good news the corrections produced

The per-merchant, per-category mandate architecture **is implementable on today's rail.**
Reserve Pay permits one block *per merchant per customer* — not one block total — so a user can
genuinely hold concurrent Blinkit, Zepto, Swiggy and IRCTC blocks, each capped at ₹10,000 for up
to 90 days, all visible in one consolidated view they can revoke from.

That removes the feasibility objection to the consumer architecture entirely. What remains is
the harder objection, which is distribution.

### 1.3 The claim that has to be retired

"The money stays in the user's account, which feels psychologically safer" is doing less work
than it appears. Funds in a Reserve Pay block are *blocked* — unavailable to the user — for up
to 90 days. Compared with UPI Autopay, the user gets guaranteed settlement and loses the
24-hour pre-debit notification. It is not obviously safer; it is differently safe, and the
difference favours the merchant.

---

## 2. The lane decision, argued both ways

### 2.1 The case FOR the consumer agent — stronger than previously credited

1. **The rail supports it now** (§1.2). No UAP dependency, no RBI dependency. This was the
   single biggest objection and it was based on a factual error.
2. **The connectivity problem is solved, and merchants solved it.** Swiggy runs MCP across three
   businesses. BigBasket closed the UPI loop. Shopify made UCP self-serve on 17 June 2026 —
   any developer registers an agent profile with no approval gate. A two-person team can reach
   real catalogues today without a single BD conversation.
3. **The cross-merchant position is genuinely unoccupied.** BigBasket's agent sells BigBasket.
   Swiggy's sells Swiggy. Nobody is the agent that compares across merchants and holds mandates
   for all of them — which is exactly where the user value is, and exactly what no merchant will
   ever build.
4. **Only the consumer agent can capture the decision-drift value.** The most defensible
   intellectual asset in this whole space (see the research report §3) is knowing what a user
   actually wanted versus what they said. That signal exists only where you own the
   conversation. Infrastructure layers never see it.
5. **No incumbency exists.** UAP is unlaunched. There is no registry, no standard, no default.

### 2.2 The case AGAINST — and why it still wins

1. **Distribution is fatal, and it is the only thing that matters.** The consumer agent is a
   distribution business wearing a technology costume. The surface is owned by ChatGPT, Gemini
   and Claude; the catalogue and margin by merchants; the rail by Razorpay, which is already
   partnered with NPCI *and* OpenAI. A two-person team with no capital enters that as the fourth
   party in a three-party deal.
2. **You would be building what your suppliers are building.** BigBasket + Razorpay + NPCI +
   OpenAI is precisely the consumer agentic stack. The reference implementation exists and is
   owned by people with catalogue, rail and surface.
3. **The economics have no floor.** UPI is zero-MDR. There are no ads to show an agent. That
   leaves consumer subscription — for an unproven utility, from an unknown brand, in the most
   price-sensitive large consumer market on earth. Indian consumers do not pay subscriptions for
   convenience software at scale.
4. **Trust is the product, and trust is exactly what a new brand cannot supply.** Asking a
   consumer to grant standing payment authority to a two-person startup is the single hardest
   sale in Indian fintech. Every trust lever in the research report §7.1 takes years of observed
   reliability to build.
5. **The team constraint is real.** The core competence here is agentic AI systems, not consumer
   growth marketing. A consumer agent is 20% agent quality and 80% CAC, retention and brand.
6. **The evidence on merchant appetite is negative.** Walmart withdrew ChatGPT Instant Checkout
   over roughly 3× worse conversion. Agent-mediated selection strips merchandising, upselling
   and brand equity. Merchants adopt defensively, not enthusiastically — which caps how much
   they will ever pay an intermediary.

### 2.3 The decision, and what would overturn it

**Decision: do not build the consumer agent.** The blocking constraint is distribution and
trust-brand, not technology or regulation — and neither is solvable by a two-person team with
grant funding.

Explicit falsifiers. If any of these becomes true, reopen the question:

| Falsifier | How you would know | By when |
|---|---|---|
| A distribution partner hands you the surface — a telco, a bank app, or an LLM platform wanting an India commerce layer | One signed pilot with a partner holding >10M users | Reopen on occurrence |
| Consumers demonstrably pay for agentic shopping in India | Any Indian consumer agent shows paid retention >30% at 6 months | Watch quarterly |
| UAP creates a licensed "agent operator" category with a registry moat | UAP draft publishes with operator licensing | On UAP publication |
| Cross-merchant agents get locked out, making the neutral aggregator scarce and valuable | Merchants restrict MCP access to first-party agents | Watch merchant terms |

### 2.4 The uncomfortable finding about the previously chosen lane

The B2B Reserve Pay decisioning wedge is **weaker than the corpus assumed**, and this should be
said plainly rather than absorbed quietly:

- Two of its three founding claims were wrong. Customers *can* revoke blocks from their UPI app;
  the "no pre-debit notification" claim is unverified and issuers *are* required to notify on
  debit.
- The compliance argument is now contested — the RBI exemption for e-mandate recurring
  transactions may cover Reserve Pay entirely.
- **There is almost nothing to screen.** The only confirmed closed-loop Indian flow has a human
  confirmation on every purchase. A pre-debit decision engine screening human-confirmed
  purchases is solving a problem that has not arrived.

It is not dead — it becomes real the moment Mode 2 volume appears — but it is a **2027 product
being sold in 2026**, and the honest position is that it needs a trigger it does not control.

---

## 3. Consumer journey

Retained because it is needed for research and for the eventual UAP submission, and because the
enterprise product reuses most of it.

**Onboarding — graduated, never all at once.**
Observe → recommend → execute-with-confirmation → execute-and-notify → execute-silently.
Promotion is earned per category against a measured record; demotion is automatic on anomaly.
Any product that starts a new user at "execute silently" will lose them at the first error.

**Mandate setup.** Per merchant, per category, on Reserve Pay: amount, expiry, and a
reversibility class. The novel field is the last one — the agent's autonomy should follow
*undoability*, not value. A ₹6,000 returnable purchase is safer to delegate than a ₹800
non-refundable one.

**The instruction.** Conversational, voice or chat, with provenance recorded: was this a human
turn, or did it originate in retrieved content?

**Discovery — where the actual product is.** This is the drift problem from the research report
§3, and the interaction model is the differentiator:
- Surface a spanning set, not a ranked list — cheapest, best-rated, and closest to the stated
  intent, explicitly labelled as such
- Disclose the ranking basis, and disclose paid placement if any ever exists
- **Name the drift out loud**: *"You said biryani. This combo is ₹80 less and rated higher, but
  it isn't biryani. Which way?"* Making the departure visible is what converts drift from a
  failure into the feature
- Ask when the decision is expensive or irreversible; do not ask when it is cheap and undoable

**Execution.** Verify price against consent-time price, check idempotency across retries,
confirm merchant authenticity, then debit against the block.

**Aftermath.** Notify with a three-question explanation — *what I understood, what I considered,
why this one* — and a one-tap undo. The undo matters more than the accuracy.

---

## 4. Enterprise journey — the recommended business

The structural advantage: **the principal and the buyer are the same legal entity.** That single
property removes consumer trust-building, consumer CAC, zero-MDR economics, UAP dependency and
RBI dependency all at once.

**Who has this problem today, in order of pain:**

1. **Ad-spend agents** — performance marketing budgets already move automatically, they are
   large, and overspend has a number attached. Best beachhead.
2. **Procurement and vendor payment bots** — statutory audit exposure under internal financial
   controls: *what was the authority for this payment, and who approved it?* Today there is no
   answer.
3. **Cloud, API and inference spend** — machine-scale, already autonomous, already over budget.
4. **SaaS renewals** — lowest urgency, easiest to instrument.

**The journey:** engineering deploys agents that touch money → finance discovers it during
audit → someone asks who authorised a payment → there is no answer → budget appears.

**Why they pay:** not compliance-by-mandate — no regulation requires agent controls yet — but
because an existing obligation has become unsatisfiable. Internal financial controls, AML
obligations and DPDP all still attach to an agent-initiated payment. **The mandate is not
missing; the evidence is.**

**What you sell:** per-agent identity chained to a verified principal; a bound credential
(virtual card or tokenised handle) where the limit is enforced at the credential, not inside the
agent; a deterministic policy engine with no model in the approval path; behavioural drift
detection per agent; and a tamper-evident decision record.

**The one-line answer to the hardest objection** — *"we already scope our agents in config"*:
that is client-side validation, for money. A limit enforced inside the agent is on the same side
of the fence as a prompt injection.

---

## 5. Connectivity — the build decision

Given the research report §5, the practical ranking for an Indian team:

| Priority | Path | Why |
|---|---|---|
| **1** | **Shopify UCP self-serve** | Register an agent profile, call the public MCP endpoint, no approval gate, live since 17 Jun 2026. Fastest route to a real catalogue |
| **2** | **Swiggy MCP** | Three businesses, 40,000+ products, published tools. **But cash-on-delivery only** — good for discovery research, useless for payment work |
| **3** | **ACP via Stripe** | Easiest checkout integration, but centralised and Stripe-locked; weak fit for India |
| **4** | **ONDC** | Structurally the best substrate and the best story. No agentic specification exists yet — treat as a research and policy bet |
| **5** | **Direct merchant APIs** | Only after a design partner asks for a named merchant |
| **Never** | **Browser automation** | Maximum injection surface, minimum defensibility. Acceptable for a demo, never for production spend |

**The strategic read:** connectivity is not a moat and will not be one. Merchants solved it in
eighteen months, and Adyen already ships a translator across UCP, ACP, AP2 and Meta's checkout.
Anyone whose plan depends on owning integrations is building a commodity.

---

## 6. Layers ranked by ten-year defensibility

Scored on: can a two-person Indian team enter, and does the position compound?

| Rank | Layer | Ten-year defensibility | Can you enter? |
|---|---|---|---|
| **1** | **Decision record / evidence corpus** | **Highest.** Cannot be built retroactively. Whoever holds decision-time records adjudicates disputes, and systems of record do not churn | Yes — it is a byproduct of any decisioning product |
| **2** | **Agent identity registry** | Very high, but **NPCI will own it in India**. Do not compete with the utility | No |
| **3** | **Behavioural model of agent-user pairs** | High — compounds with data, and is the one signal that works when no human is touching a device | Yes, with volume |
| **4** | **Enterprise spend control** | Medium-high — the Ramp/Brex shape: sticky, budget-owning, expands per agent | **Yes. Recommended** |
| **5** | **Pre-debit decisioning** | Medium — real, but NPCI may specify it and PSPs may build it | Yes, when volume arrives |
| **6** | **Mandate/consent format** | Low — AP2 won and is now under FIDO governance. Consume it | No |
| **7** | **Merchant connectivity** | **Lowest.** Commoditised inside eighteen months | Yes, and don't |
| **8** | **Consumer agent** | Low as a defensible layer — it is a distribution business | Technically yes, practically no |

**What actually compounds, in order:** the decision-record corpus, the standards position (a
submitted UAP consultation response and a reference implementation are cheap now and impossible
to acquire later), and per-agent behavioural baselines.

---

## 7. Five-year roadmap

Gated on milestones, not calendar dates, because the two biggest dependencies — UAP publication
and Mode 2 volume — are outside your control.

### Phase 0 — Prove the problem exists (0–3 months)
- Ten conversations: five enterprise engineering leads running agents that touch spend, three
  PSP risk leads, two bank compliance
- **Answer the three blocking questions**: is there any agent transaction volume to screen; does
  Reserve Pay fall inside RBI's e-mandate exemption; will UAP specify liability or only
  authorisation
- Build the enterprise demo: an agent blocked outside its mandate, replayable in an audit view
- Submit the UAP consultation response — free distribution and the standards position
- **Gate:** two enterprises confirm uncontrolled agent spend they can quantify. If not, stop.

### Phase 1 — First revenue, enterprise only (3–12 months)
- Two to four paying customers on ad-spend or procurement agents
- Per-agent credential + policy engine + decision record shipped
- Publish the injection-surface result (research report R5) — technical credibility is the
  cheapest marketing available to this team
- **Gate:** one customer renews and expands agent count. Renewal is the only real signal.

### Phase 2 — Become the evidence layer (12–24 months)
- Decision record becomes a product: audit packs, oversight reports under FREE-AI
- One bank or NBFC on the compliance SKU — annual, budgeted, volume-independent revenue
- Add UPI Reserve Pay decisioning **if and only if** Mode 2 volume has appeared
- **Gate:** compliance revenue exceeds per-decision revenue. If it does, you are an evidence
  company, and price accordingly.

### Phase 3 — Ride the rail, if it arrives (24–42 months)
- **Trigger: UAP publishes and RBI approves.** Not before
- Consume UAP mandate objects; aim to be the reference implementation
- PSP distribution: one integration, many downstream merchants
- Consumer surface **only** as a free trust feature funded by B2B — a dashboard where users see
  and kill agent mandates. Never as the business
- **Gate:** if UAP specifies decisioning *and* someone else ships the reference implementation,
  stop investing here and stay enterprise

### Phase 4 — Export the position (42–60 months)
- The rail-specific work does not export; the evidence and identity layer does
- Two paths, decided by what the data shows: (a) the neutral dispute-adjudication layer for
  agent commerce, defensible because no party to a dispute can credibly write its own evidence;
  or (b) acquisition by a PSP, network or identity vendor, for which the decision-record corpus
  is the asset being bought
- **Gate:** if the corpus is not demonstrably improving decisions by month 42, there is no
  compounding asset and this is a services business — price and sell it as one

### The four kill conditions
Stop if any of these becomes true:
1. UAP specifies instruction verification *and* mandates a reference implementation someone else ships
2. A funded incumbent ships India agentic decisioning before you have two live design partners
3. Customers cannot pass you the agent's reasoning trace, reducing you to rules they can write
4. Enterprise agent spend turns out to be governed adequately by existing config and nobody buys

---

## Appendix — what to verify before pitching any of this

1. **Does Reserve Pay fall inside RBI's e-mandate exemption?** Determines whether a compliance
   market exists at all. Ask a bank compliance lead or a Big Four financial services risk partner
2. **₹10,000 per block or per month?** Sources conflict. All volume arithmetic depends on it
3. **Is there any human-absent agentic flow live in India?** Every confirmed flow has a human
   confirmation step. If none exists, the decisioning product has no 2026 market
4. **What does an enterprise actually pay today** for spend controls, and against which budget
   line — spend management, fraud, or audit
5. **Whether merchants will restrict MCP access to first-party agents** — this determines
   whether the neutral cross-merchant position ever becomes valuable (falsifier 4 in §2.3)
