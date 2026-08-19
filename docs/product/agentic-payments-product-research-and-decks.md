# Agentic Payments: Product Research + Two Decks

**Working company name:** Warrant · **Product A:** Warrant Interlock (pre-debit control plane) · **Product B:** Warrant Ledger (consent, intent & dispute evidence)
Date: 28 July 2026 · Status: pre-validation, pre-build

---

## TL;DR — the one thing the research changed

I proposed two products last conversation. The research says one of them is contested and one is nearly empty, and I had the emphasis backwards.

- **The firewall (pre-transaction) is crowded.** Google's AP2 already specifies signed Intent → Cart → Payment mandates. Visa has Trusted Agent Protocol for agent verification. Mastercard has Agent Pay with Verifiable Intent and did a live end-to-end agent payment with Santander in March 2026. Stripe/OpenAI shipped protocol work. Nekuda, Skyfire and Basis Theory have raised roughly $50M combined on agent wallets, identity and vaults — Nekuda's round included Visa Ventures and Amex Ventures, i.e. the networks are funding this layer directly.
- **The dispute and liability layer (post-transaction) is explicitly unbuilt, and everyone says so.** The Payment Dispute Institute's framing: "the agent carries no financial liability, even though it now makes the purchase decision." Liability defaults to the merchant of record. Chargebacks911 says the industry is building agentic commerce "from the wrong end."
- **India is the defensible surface for both.** UPI disputes don't run on card-network rules — they run through NPCI's UDIR, which has no concept of an agent. Agentic UPI is already live in pilot on UPI Reserve Pay. NPCI's Unified Agent Protocol is in industry consultation *right now*, RBI approval pending. That's a standards seat that will not be open in twelve months.

**Verdict:** build A as the wedge, B as the company. A prevents loss and gets you deployed; B becomes the system of record and can't be built by anyone who didn't capture the data A captures. Do not pitch A as a global agent-security play — you will be compared to Visa, and lose.

---

# PART 1 — PRODUCT RESEARCH

## 1.1 What happened in the last twelve months

| Date | Event | Why it matters to you |
|---|---|---|
| Dec 2024 | RBI constitutes FREE-AI committee | The compliance hook that pays for audit trails |
| Aug 2025 | RBI FREE-AI framework released — 7 sutras, 6 pillars, 26 recommendations; model risk management + human oversight over autonomous AI at banks, NBFCs, payment systems | Regulated buyers will be *required* to evidence oversight of agents |
| 16 Sep 2025 | Google announces AP2 with 60+ partners (PayPal, Mastercard, Amex, Adyen, Coinbase, Worldpay, JCB, UnionPay) | The mandate format is decided. Don't reinvent it — implement it |
| Late 2025 | Visa Trusted Agent Protocol + Intelligent Commerce; aligned with OpenAI's ACP and Coinbase x402 | Agent-vs-bot verification is a network function now |
| 15 Feb 2025 → 15 Jul 2025 | NPCI chargeback addendum (UPI-OC-No-184-B) and reprocessing changes take effect | UPI dispute plumbing was *just* revised — before agents existed on it |
| 20 Feb 2026 | **Razorpay + NPCI launch agentic payments on Claude** — closed pilot, UPI Reserve Pay, Zomato/Swiggy/Zepto | Agents are transacting on UPI today, in production, in India |
| Mar 2026 | Mastercard + Santander complete Europe's first live end-to-end agent payment on live bank infrastructure; Stripe/OpenAI protocol work ships | Authorization is solved-ish globally; disputes are not |
| 8 Jul 2026 | Business Standard: NPCI developing **Unified Agent Protocol** in consultation with industry, extending UPI Circle delegated payments; RBI approval required | Twenty days ago. The window |

## 1.2 Who owns which layer

| Layer | Owner today | Open to you? |
|---|---|---|
| Mandate format / consent semantics | AP2, Mastercard Verifiable Intent | **No** — adopt it |
| Agent identity & bot verification | Visa TAP, Skyfire KYAPay | **No** |
| Agent wallet, card credential, spend caps | Nekuda, Basis Theory, Clink, network tokens | **No** |
| Rails & settlement | UPI/NPCI, card networks, PSPs | **No** — licence + capital wall |
| **Pre-debit decisioning on UPI Reserve Pay mandates** | Nobody, India-specific | **Yes** |
| **Agent-aware dispute evidence & adjudication** | Nobody, anywhere | **Yes — biggest gap** |
| **Agent oversight evidence for FREE-AI compliance** | Nobody | **Yes** |

## 1.3 The failure taxonomy — what actually goes wrong

This is the core product research. Every row is a real failure mode of an agent holding a payment mandate, and today every row lands on a human who didn't cause it.

| # | Failure | Example | Who eats it today |
|---|---|---|---|
| 1 | Intent misread | "Order my usual" → wrong variant, wrong quantity | Merchant (MoR liability) |
| 2 | Price drift | Price at consent ≠ price at debit; surge, delivery fee, dynamic pricing | User disputes; merchant absorbs |
| 3 | Duplicate execution | Agent retries on timeout; two debits against the same reserve | Merchant/PSP reversal cost |
| 4 | Scope creep on a reserve | Reserve Pay allows multiple partial debits over up to 90 days — agent keeps drawing beyond what the user pictured | User, discovering it late |
| 5 | Indirect prompt injection | Poisoned web content or SEO-seeded pages instruct the agent mid-task (documented by Zscaler ThreatLabz and others) | Nobody knows — no framework |
| 6 | Fake or spoofed merchant | Agent transacts with a merchant a human would have distrusted | User; recovery unclear |
| 7 | Stale consent | Mandate still valid, user's intent long expired | User |
| 8 | Agent identity ambiguity | Which agent, which version, which model, acting for whom | Unattributable — the core evidentiary hole |
| 9 | No reason code | UDIR reason codes assume a human acted or a transaction failed. "The agent misunderstood" maps to nothing | Dispute dies or gets miscoded |
| 10 | No oversight record | Bank/NBFC must evidence human oversight of autonomous systems under FREE-AI | Compliance team, manually |

Rows 1–7 are what Product A prevents. Rows 8–10 are what Product B makes adjudicable. Row 9 is the single sharpest fact in this document: **India shipped agent-initiated payments onto a dispute system that has no reason code for an agent's mistake.**

## 1.4 Why India, specifically

Not patriotism — structure. UPI is NPCI's rail, not Visa's. Visa's TAP and Mastercard's Agent Pay solve agent trust *on card rails*; they do not extend into UPI, and NPCI is writing its own protocol instead. That means the agent-trust problem on the world's highest-volume retail payment system is being solved locally, by a consultation you can physically attend, on a dispute framework (UDIR) that is documented, API-driven, and agent-blind. A two-person team in India has a genuine right to win here that it does not have on card rails.

Second reason: UPI Reserve Pay is a *weirder* liability surface than a card token. Funds blocked in the user's account for up to 90 days, multiple partial debits against the pool, spend limit set once per merchant. Nothing global is designed for that shape.

## 1.5 Buyers and jobs-to-be-done

| Buyer | Their job | Which product | Why they pay |
|---|---|---|---|
| PA/PSP risk team (Razorpay, Cashfree, PayU, Juspay, Pine Labs) | Don't let agentic volume blow up my dispute ratio | A then B | Direct P&L; they carry reversal cost |
| Merchant platform (quick commerce, travel, food) | Don't eat returns for an agent's misread | A + B | MoR liability sits on them |
| Bank / NBFC (mandate issuer) | Evidence oversight of autonomous systems for RBI | B | FREE-AI |
| Agent builder (anyone shipping a shopping agent in India) | Get approved to transact at all | A | Gate to distribution |
| NPCI / policy | Make UAP enforceable, not just specified | Reference implementation | Standards influence, not revenue |

**Primary buyer for week one: PA/PSP risk teams.** They have budget, they have the loss, they are ~8 companies, and they all answer email.

## 1.6 Repositioning verdict

- **A is not "an agent payment firewall."** That framing loses to Visa TAP. A is **a pre-debit decision engine for UPI Reserve Pay mandates** — the checks the Indian rail specifically needs and nobody global is building.
- **B is not "we invent a consent ledger."** AP2 invented the format. B is **the evidence store and adjudication engine that turns AP2/UAP mandates into a UDIR-filable dispute and a FREE-AI-defensible audit record.**

---

# PART 2 — DECK A: Warrant Interlock

*Pre-debit control plane for agent-initiated UPI payments*

**Slide 1 — Title**
Warrant Interlock. The check that runs before an AI agent spends your customer's money.
*Note: lead with the Razorpay/NPCI pilot date. Agents are live on UPI. This is not a future problem.*

**Slide 2 — The shift**
On 20 Feb 2026, Razorpay and NPCI put AI agents on UPI Reserve Pay in production pilot — a user sets one spend limit, and an agent debits against it repeatedly for up to 90 days. NPCI is now writing the Unified Agent Protocol to scale this. The authorization exists. The *judgment* before each debit does not.

**Slide 3 — The problem**
Seven ways an agent debits wrongly: misread intent, price drift between consent and debit, duplicate retries, scope creep across a 90-day reserve, prompt injection from poisoned web content, spoofed merchants, stale consent. All seven are invisible to the mandate — the mandate only knows the limit wasn't breached.

**Slide 4 — Who eats it**
Liability follows the merchant of record. The agent carries none. The PSP absorbs reversal cost and dispute-ratio damage. Nobody in the chain currently has a pre-debit veto that understands *what the user actually meant*.

**Slide 5 — Product**
An inline API call between agent intent and payment execution. Returns allow / block / step-up in under 150ms, with a reason. Checks: mandate scope, semantic match between intent and cart, price delta vs consent-time price, duplicate/idempotency across agent retries, cumulative draw against the reserve, merchant reputation, injection-signature detection on the agent's context, and behavioural drift for that agent-user pair.
*Note: the semantic and injection checks are the parts a rules engine can't do. That's the moat and that's your day job.*

**Slide 6 — Architecture**
Sits beside the PSP, not in the money path — no funds custody, so no PA-CB licence, no net-worth bar. Consumes AP2/UAP mandate objects. Emits a signed decision record to Warrant Ledger (Product B). Fail-open or fail-closed is the customer's toggle.

**Slide 7 — Why now**
Live pilot volume today; UAP consultation open today; RBI FREE-AI already requires oversight of autonomous systems. Twelve months from now the protocol is frozen and the incumbents' risk stacks have an agentic module.

**Slide 8 — Why we don't collide with Visa or Nekuda**
Visa TAP verifies *that* an agent is legitimate, on card rails. Nekuda gives an agent a wallet with caps. Neither evaluates whether *this specific debit* matches *this specific consent* — and neither operates on UPI Reserve Pay, because UPI isn't theirs. We are the decision layer on the Indian rail, and we consume their identity primitives rather than competing with them.

**Slide 9 — Competition, honestly**
Adjacent and funded: Nekuda ($5M Series A, Madrona, with Visa Ventures and Amex Ventures), Skyfire, Basis Theory, Clink. Indian incumbents who could build it: Razorpay's and Juspay's own risk engines, Bureau, Signzy. Our answer is speed, protocol proximity, and the fact that in-house risk teams are queued behind the roadmap for a volume that is still in pilot.

**Slide 10 — Go to market**
Eight PA/PSPs are the entire beachhead. Design-partner deal: free integration, we take logged decisions as our data right, they take a named allow/block report. Then per-decision pricing.

**Slide 11 — Business model**
Per screened intent (sub-paisa at scale, priced in ₹ per thousand decisions), floor via platform fee. Enterprise SKU for banks bundling the FREE-AI evidence pack. Design partners free for 90 days.

**Slide 12 — What exists in seven days**
Working demo on the Razorpay sandbox: an agent that gets prompt-injected mid-task and tries to debit a spoofed merchant at a drifted price; Interlock blocks it, shows the reason, emits the signed record. Two-person build, entirely inside our competence.

**Slide 13 — Team**
Two founders shipping production agentic systems for DRDO / Government of India at Genrise. Governed autonomy under audit is not a pivot for us; it's the work we already do. Seeking one banking/NPCI-side advisor.

**Slide 14 — Risks**
NPCI specifies parts of this into UAP → we become the reference implementation, which standards bodies never build. Volume is pilot-stage → design partnerships and grant funding, not MRR, in 2026. Latency budget is unforgiving → fail-open default and cached decisions.

---

# PART 3 — DECK B: Warrant Ledger

*Consent, intent and dispute evidence for agent-initiated payments*

**Slide 1 — Title**
Warrant Ledger. When an AI agent buys the wrong thing, someone has to prove what the human agreed to.

**Slide 2 — The gap everyone names**
The Payment Dispute Institute: the agent carries no financial liability though it makes the decision. Chargebacks911: the industry is building agentic commerce "from the wrong end," without dispute infrastructure. All three card networks shipped agent *authorization* by March 2026. None shipped agent *adjudication*.

**Slide 3 — The India-specific version, and it's sharper**
UPI disputes run through NPCI's UDIR — participant-to-participant reversals over APIs, governed by UPI-OC-No-184 and its Feb 2025 addendum. Those reason codes were written for failed, unauthorized or fraudulent *human* transactions. "The agent misunderstood my instruction" maps to no code. Agentic UPI went live in February anyway.

**Slide 4 — Product**
An append-only, signed evidence store for every agent-initiated payment: the consent artifact and its scope, the price and cart contents at consent time, the agent's identity and version, the reasoning trace and tool calls that produced the intent, the pre-debit decision from Interlock, and the debit outcome. Queryable, retainable, replayable.

**Slide 5 — The output that gets paid for**
Not a database — three artifacts. (1) A **dispute pack**: the one-page, UDIR-mappable evidence bundle a PSP files or defends against. (2) A **replay**: deterministic reconstruction of what the agent saw and decided, for adjudication. (3) A **FREE-AI oversight report**: standing evidence for a bank that its autonomous systems are governed.

**Slide 6 — Why it's defensible when the format isn't**
AP2 defines the mandate; UAP will define the Indian one. Formats are commodities. Retention, verification, cross-party querying, reason-code mapping and adjudication are products — and they require having captured the data at decision time, which is exactly what Interlock does. Nobody can retroactively adjudicate what they never recorded.

**Slide 7 — Why now**
Disputes lag transactions by weeks. Agentic UPI volume started in February. The first wave of agent-caused disputes is arriving into a system with no reason code for them, right now.

**Slide 8 — Market signal, with a caveat**
Vendor research claims a 4,700% jump in AI traffic to retail sites and projects ~24% chargeback growth through 2028; security vendors report a sharp rise in prompt-injection attacks in 2026. Treat the exact numbers as marketing; the direction is corroborated across independent sources.

**Slide 9 — Buyers**
PSP dispute operations (cost per dispute, win rate). Merchant platforms (they're liable). Banks and NBFCs (FREE-AI evidence). Eventually NPCI itself, as the reference implementation of agent-aware dispute handling.

**Slide 10 — Business model**
Per-dispute-pack fee plus retention-based platform fee — the shape dispute vendors already buy. Compliance SKU for regulated entities, priced annually. Becomes the system of record, and systems of record don't churn.

**Slide 11 — Wedge sequencing**
Interlock is sold on loss prevention and gets us instrumented. Ledger is sold on liability and makes us structural. Same integration, same call, one deployment. This is why they're one company, not two.

**Slide 12 — What exists in seven days**
A dispute pack, generated from the demo's blocked and allowed transactions, mapped against actual UDIR reason codes with the gaps marked in red. That red-marked page is the entire pitch.

**Slide 13 — Team & standards position**
Government-grade agentic systems experience, plus an active submission into the UAP industry consultation. The goal is to be the team NPCI's protocol authors call.

**Slide 14 — Ask**
Two paying or committed design partners among the eight Indian PSPs; SIIC grant; one banking advisor. Twelve-week milestone: agent-caused disputes filed and defended through UDIR using Warrant evidence.

---

# PART 4 — Open questions to close on calls this week

Each maps to a person who can answer it. Do not build past these.

1. **Does agentic dispute volume exist yet?** — PSP risk lead. If pilot volume is tiny, B is a thesis and A is the product.
2. **Which UDIR reason code do PSPs use today for an agent's error?** — PSP dispute ops. If they've invented a workaround, that workaround is your spec.
3. **Who is contractually liable in the Razorpay/NPCI pilot?** — pilot merchant or Razorpay partnerships. The contract already had to answer this.
4. **Is UAP going to specify liability, or only authorization?** — anyone in the consultation. This determines whether B is your product or NPCI's.
5. **Is there a latency budget an inline check can live inside on Reserve Pay?** — PSP engineer. If it's under 50ms, A must be async advisory rather than blocking.
6. **Do banks read FREE-AI as requiring per-transaction agent evidence?** — bank compliance or a Big Four financial-services risk partner. This is B's compliance revenue, or isn't.
7. **What does a PSP pay per dispute today?** — anchors B's pricing.

## Verify before you pitch

Sourced from secondary coverage and worth confirming against primary documents: the UDIR circular numbers and effective dates; whether Stripe/OpenAI's March 2026 protocol work is named as reported; the exact status of UAP in consultation; and Nekuda's round details. The Razorpay/NPCI launch, AP2's mandate architecture and FREE-AI's structure are from primary or near-primary sources.

## Sources

- Razorpay × NPCI agentic payments launch — https://razorpay.com/blog/agentic-payments-and-npci/
- AP2 protocol — https://ap2-protocol.org and Google Cloud announcement, 16 Sep 2025
- NPCI Unified Agent Protocol — Business Standard, 8 Jul 2026
- RBI FREE-AI framework — rbi.org.in press releases, Dec 2024 / Aug 2025
- NPCI UDIR and chargeback rules — npci.org.in, UPI-OC-No-184 series
- UPI Reserve Pay mechanics — Pine Labs, Cashfree and PayU developer documentation
- Agent liability gap — Payment Dispute Institute; Chargebacks911; National Law Review, "When AI Clicks Pay"
- Agent payment infrastructure funding — Nekuda, Skyfire, Basis Theory coverage
- Visa Trusted Agent Protocol / Intelligent Commerce; Mastercard Agent Pay + Santander pilot, Mar 2026
- Indirect prompt injection research — Zscaler ThreatLabz and related 2026 security reporting
