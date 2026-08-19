# Agentic Commerce and Payments in India
## A research report: what breaks, what is unbuilt, and what is worth publishing

**7 August 2026.** Self-contained. Facts trace to `agentic-payments-fact-base-2026-08.md`;
claims that contradict earlier internal documents are listed in `corpus-corrections-2026-08.md`.

---

## 0. The argument in one page

India put AI agents onto a live payment rail in February 2026 and is now writing the protocol
that will govern them. Every protocol shipped worldwide in the last eighteen months — AP2, UCP,
ACP, Visa TAP, Mastercard Agent Pay, and the proposed NPCI Unified Agent Protocol — answers the
same question: **how does an agent obtain permission to pay?** That question is close to solved.

Three questions after it are not:

1. **Who gave this instruction?** There is exactly one strong authentication event in an
   agentic UPI payment — the UPI PIN at mandate creation. Everything after is triggered by a
   sentence in a chat window with no PIN, no device binding, and no speaker verification.
2. **Did the purchase reflect what the human wanted?** — and this report's central claim is that
   this question is *malformed*, because the thing it presupposes does not exist.
3. **Can anyone prove what happened?** UDIR has no reason code for an agent's mistake.

The central contribution proposed here concerns (2). Every mandate architecture in production
treats **intent as an object that exists prior to shopping and can therefore be signed at
t₀**. Fifty years of consumer research says the opposite: preference is *constructed during*
the encounter with the choice set. If that is right, an intent mandate can be cryptographically
perfect and semantically empty — and worse, the agent that searches on the user's behalf is
itself one of the forces constructing the preference it will later be judged against.

That is not a user-experience problem. It is a **validity** problem for the entire consent
chain, and no protocol currently has a place to put it.

---

## 1. Critique of the framing — including my own

Before building on the standard problem statement, four corrections to it.

### 1.1 "Mandate" is three different things wearing one word

The field's vocabulary hides a category error. Everything currently called a mandate does one
of three jobs:

| Job | What it proves | Who does it |
|---|---|---|
| **Authority binding** | A human once agreed to a spending envelope | UPI Autopay, Reserve Pay, AP2 Intent Mandate |
| **Actor binding** | The requester is a specific registered agent, not a bot | Visa TAP, Mastercard Agent Tokens, NPCI UAP registration |
| **Origin binding** | *This particular instruction* came from the principal | **Empty set** |

The stack is being assembled as though the first two compose into the third. They do not, and
saying so precisely is more than half the contribution of any paper in this area.

### 1.2 The instruction-origin gap is real but no longer novel *as an observation*

`arXiv:2604.15367` (*SoK: Security of Autonomous LLM Agents in Agentic Commerce*) explicitly
names **"standardised authentication for instruction origin validation"** among its open
research gaps. This is good news for the framing — the problem is real and citable — and bad
news for anyone planning to contribute the observation itself.

**Consequence for the thesis:** a paper whose contribution is *"nobody verifies instruction
origin"* is now a literature review. A paper whose contribution is *a mechanism that verifies
it, with an evaluation*, is a contribution. Plan accordingly.

### 1.3 The regulatory argument is weaker than commonly stated

A widespread reading holds that RBI's Authentication Directions, 2025 (effective 1 April 2026)
require two factors with one dynamic per payment, that agent debits cannot produce a dynamic
factor, that agent payments are not exempt, and therefore that every agentic UPI debit is
non-compliant with full issuer liability.

The exemption list **includes "recurring transactions under the e-mandate framework."** Whether
UPI Reserve Pay sits inside that framework for exemption purposes is unresolved and, as far as
can be established, unaddressed publicly by either RBI or NPCI.

This is a better research question than a premise. It has a binary answer with large
consequences, it is answerable by asking the right person, and no published work addresses it.

### 1.4 A hidden contradiction in the standard consumer design

Nearly every proposed consumer architecture — including the category-mandate design this report
was commissioned to evaluate — contains a step reading *"obtain final approval from the user"*
somewhere between cart assembly and payment.

If that step is present on every purchase, the system is **human-present agent-assisted
checkout**. Existing two-factor authentication works, the instruction-origin problem largely
evaporates, the regulatory collision disappears — and so does most of the claimed value, since
the user is still making every decision. What has been built is a better search engine with a
payment button.

If that step is absent, all three problems return at once.

The interesting design space is precisely the middle: **which purchases earn an approval step,
decided by something other than the agent that wants to proceed.** Every serious contribution
in this field lives in that sentence.

---

## 2. A ladder, not a binary: distance from the human to the debit

The productive axis is not *what agents buy* but *how far the human is from the moment money
moves*. That distance determines which safeguard fails.

| Mode | Human's position | Live example (Aug 2026) | What breaks |
|---|---|---|---|
| **0 — Agent-assisted** | Present at debit; approves the cart | BigBasket on ChatGPT: agent presents options, **one human confirmation**, Razorpay executes on Reserve Pay | Nothing structural. Existing 2FA holds |
| **1 — Human-triggered, agent-executed** | Present at *instruction*, absent at *debit* | Razorpay/NPCI pilot, Feb 2026 | Presence assumption; underspecification. Origin is *probably* the principal — "probably" is load-bearing |
| **2 — Standing intent** | Absent at both; scope set once, agent acts for days or weeks | AP2 Intent Mandate (human-not-present); a 90-day Reserve Pay block *is* standing intent | Presence, instruction-origin, and the veto window — **there is no instruction at debit time** |
| **3 — Agent-to-agent** | Absent on both sides of the trade | x402 on Base; Stripe/Tempo MPP; programmatic ad buying, machine-to-machine for 15 years | Everything downstream: nobody to notify, nobody to dispute, values too small for human-scale controls |
| **4 — Agent as economic actor** | Delegated treasury; agents paying agents | Early, mostly crypto-side | Legal personality. Blocked on law, not engineering |

### 2.1 What the ladder reveals

**India shipped the rail for Mode 2 before shipping any control for it.** A Reserve Pay block
is ₹10,000 of standing authority, live for 90 days, drawn down by multiple debits, with no
UPI PIN after creation. That is Mode 2 by construction. Yet every *confirmed* live Indian
agentic flow today sits at Mode 0 — BigBasket requires a human confirmation; Swiggy's MCP
integration does not even close the payment loop, offering **cash on delivery only**.

So the gap between deployed capability and deployed usage is currently wide, and the safety
question is what happens as that gap closes.

**The transition from Mode 1 to Mode 2 changes the nature of the problem.** At Mode 1 the
question is *did this sentence come from the principal* — an authentication question, in
principle answerable with device, session and speaker signals. At Mode 2 **there is no
sentence**. The agent decided that today is the day. The question silently becomes *does this
action fall within a scope the principal signed* — a **verification** question about semantic
fit, not an authentication question about a speaker.

AP2 built the artifact for Mode 2 and left the verifier undefined. UPI built the rail for Mode 2
and built neither. That undefined verifier is where the research is.

---

## 3. The decision drift problem: why signed intent may be semantically empty

This is the report's principal claim.

### 3.1 The assumption every protocol makes

Formally, the shared model is:

> A principal at time t₀ holds an intention *I*. A mandate *M* encodes a scope *S* ⊇ *I*, signed
> by the principal. At t₁ the agent selects purchase *p*. The system's validity check is
> **p ∈ S**. If it passes, the payment is authorised and correctly authorised.

AP2 implements this literally: an Intent Mandate scoped to seller, category, price ceiling and
time window, with the agent permitted to generate the Cart Mandate itself *if the Intent
Mandate's conditions are precisely met*. UAP's design — registration, verification, limits,
consent controls — is the same shape. So is a per-merchant, per-category spending limit.

An independent commentary on AP2 states the limitation almost exactly:

> *"An AP2 mandate verification only says the mandate covered the action, not that the action
> satisfied the obligation — the mandate constrains what the agent could do, not whether the
> agent did the right thing."*

That is correct, and it is treated in the literature as a caveat. It is not a caveat. It is a
consequence of a false premise, and the premise is repairable only by changing what a mandate is.

### 3.2 What consumer research actually says

The premise is that *I* exists at t₀. Constructive preference theory — Bettman, Luce and Payne,
*Constructive Consumer Choice Processes* (1998), and the tradition following Slovic and
Lichtenstein — holds that for any decision of moderate complexity or unfamiliarity, preferences
are **constructed at the point of elicitation**, not retrieved from a stable stored ordering.
Choices are sensitive to the composition of the choice set, the order of presentation, the
framing of attributes, the presence of decoys, and the effort/accuracy tradeoff the decision
maker is willing to make.

The everyday version is the one that motivated this report: a user intends *veg biryani*,
browses, finds restaurant A poor value, B offering an above-₹299 discount, C bundling a better
combo, and buys from Taco Bell. Nothing went wrong. That is what shopping **is**.

### 3.3 The formal problem: endogeneity

Combining the two gives something sharper than "intent is underspecified."

Underspecification says: a true *I* existed and was imperfectly expressed. Fix it with better
elicitation. That is a solvable engineering problem and there is a large, well-funded NLP
literature working on it.

**Constructed preference says something stronger: there was no *I* to express.** The preference
relation ≽ that would justify purchase *p* does not exist at t₀. It comes into being at t₁, and
critically —

> **the agent's own search behaviour is one of the causes of the preference it will later be
> evaluated against.**

The agent chooses which options to surface, in what order, with which attributes salient. Under
constructive preference, those choices *partly determine* the preference. So the agent both
constructs and satisfies the standard by which it is judged. **The evaluation is endogenous.**

Three consequences follow, and each is a publishable claim:

**C1 — Intent-scope verification is not a validity test.** *p ∈ S* is necessary and nowhere near
sufficient. It cannot become sufficient by tightening *S*, because the gap is not scope width
but the non-existence of the referent at signing time.

**C2 — Consent to a scope is not consent to a purchase**, in a stronger sense than the legal
literature currently supposes. A signature at t₀ certifies a *constraint*, not an *authorisation
of any particular act within it*. Current liability reasoning treats the two as equivalent.

**C3 — Agent selection is an authorization problem, not a ranking problem.** If the agent's
presentation constructs the preference, then "which options the agent surfaces" is part of the
consent chain and belongs inside the audit record. No protocol records it. This links directly
to answer-engine optimisation: if merchants optimise for agent visibility rather than product
quality, they are optimising *against a buyer who has no independent preference to defend
itself with*.

### 3.4 Empirical anchors that already exist

- **ShoppingBench / Shopping Companion (`arXiv:2603.14864`)**: constraint violations account
  for roughly **25% of failure modes** in state-of-the-art shopping agents; multi-turn task
  success sits near **35%**. Mandate overreach is not hypothetical — it is a quarter of observed
  failures, measured before any money was at stake.
- **`arXiv:2606.18005`, LLM Consumer Behavior Theory** (Jun 2026): the nearest prior work,
  grounding LLM consumer choice in utility theory and behavioural economics with an
  agent–principal framing. It is the natural related-work anchor and, importantly, it does
  **not** address authorization scope.
- **No work found bridging constructed-preference theory to agent payment authorization.**
  Searched August 2026. This is the open niche.

### 3.5 What a solution would have to look like

If intent is constructed, a mandate cannot be a *specification*. The candidates:

1. **Mandate as a procedure, not a predicate.** Sign the *decision process* — "surface at least
   k options spanning this price range, disclose the ranking basis, apply no supplier-paid
   placement" — rather than the outcome. Verification becomes process compliance, which is
   auditable in a way that semantic fit is not.
2. **Regret-bounded delegation.** Bound not the spend but the *reversibility*: the agent may
   act autonomously exactly where the decision is cheaply undoable, and must escalate where it
   is not. Return policy becomes an authorization input.
3. **Preference-elicitation-as-consent.** Treat the clarifying question as the consent event.
   The moment the agent asks and the user answers is the only point where a preference
   demonstrably exists — record *that*, timestamped and signed, as the mandate.
4. **Two-sided disclosure.** Record what the agent showed alongside what it bought, making the
   construction process itself part of the dispute evidence.

Option 3 is the most immediately implementable and maps cleanly onto the "when should the agent
ask?" question. Option 1 is the most academically interesting and is the one a standards body
could actually adopt.

---

## 4. Existing mechanisms, scored

A common rubric across everything currently deployed. Columns are the three binding jobs from
§1.1 plus drift.

| Mechanism | Authority | Actor | Origin | Drift | Debit-time control |
|---|---|---|---|---|---|
| **UPI Autopay / e-mandate** | ✅ AFA at registration | ➖ | ❌ | ❌ | Pre-debit notification 24h; per-txn AFA above threshold |
| **UPI Reserve Pay** | ✅ PIN at block creation | ➖ | ❌ | ❌ | Post-debit notification only; revoke available in app (spec) |
| **UPI Circle — partial** | ✅ | ✅ person | ✅ **PIN per transaction** | ❌ | Full — but requires a human every time |
| **UPI Circle — full** | ✅ | ✅ person + device | ➖ delegate's own PIN | ❌ | ₹15k/month cap |
| **Card tokenisation** | ➖ | ✅ credential↔merchant | ❌ | ❌ | Prevents replay only |
| **AP2** | ✅ signed VC | ✅ via A2A Agent Card | ⚠️ human-present only | ❌ | Cart Mandate when human present |
| **UCP** | via AP2 | ✅ | ⚠️ inherits AP2 | ❌ | Merchant-hosted |
| **ACP** | ⚠️ Shared Payment Token | ✅ | ❌ platform session auth | ❌ | Scope on token |
| **Visa TAP** | ➖ | ✅ HTTP-edge attestation | ❌ explicitly not | ❌ | — |
| **Mastercard Verifiable Intent** | ✅ | ✅ | ⚠️ credential chain | ❌ | Built for dispute adjudication |
| **NPCI UAP (proposed)** | ✅ | ✅ registry | ❌ inherits Circle | ❌ | Unknown — unpublished |

**Reading the table.** The Origin column is empty except where a human presses something. The
Drift column is empty without exception. Nobody has built a debit-time control that does not
reduce to either a cap or a human tap.

### 4.1 The two partial precedents worth studying

**UPI Circle partial delegation** is the existence proof that India already knows how to verify
instruction origin — it just costs a human per transaction. Any product in this space is
arguably "partial delegation, where the second factor is evidence instead of a PIN."

**The Account Aggregator consent artifact** (ReBIT specification) is the stronger structural
precedent and is largely absent from the agentic-payments discussion: a signed, machine-readable,
purpose-coded, time-bounded, revocable consent object with a consent ID and a mandatory consent
audit log. It is the Indian regulatory template for exactly the artifact this domain needs, and
citing it converts "here is a novel scheme" into "here is an existing Indian pattern applied to
a new transactor" — a much easier argument in an NPCI room.

---

## 5. Merchant connectivity as a trust-boundary problem

The integration question is usually asked as a scalability question. It is more usefully asked
as: **which party can forge what, at which layer?**

| Mode | How it works | What an attacker controls | Forgeable surface |
|---|---|---|---|
| **Browser automation** | Agent drives a real browser | **The entire rendered page**, including invisible text, ARIA labels, injected DOM | Total. Every token the agent reads is adversary-controllable |
| **MCP server** | Merchant exposes typed tools | Server is authenticated; **tool *results* are not** — product titles, descriptions, reviews | Content inside authenticated envelopes |
| **Merchant REST API** | Direct integration | Same as MCP, plus bilateral contracts | Content, narrower schema |
| **ACP / UCP** | Standardised agentic checkout | Merchant-hosted (UCP) or platform-mediated (ACP) | Content; ACP concentrates trust in one platform |
| **ONDC** | Open network, schema-constrained catalogue | Seller app populates schema fields | **Narrowest** — no free-text rendering surface required |
| **x402 / MPP** | Machine-native payment at the protocol edge | No content layer at all | Minimal; but also no product semantics to verify |

### 5.1 The finding that matters

**Integration richness and injection surface move together.** Browser automation is the most
universal and the least defensible; x402 is the most defensible and carries no product meaning.
Every architecture is a choice on that curve, and nobody states it that way.

### 5.2 The India-specific argument nobody is making

**ONDC is structurally the safest agentic substrate available anywhere**, and not for the
reasons usually cited. Because it is a schema-constrained open network rather than a rendered
storefront, a compromised seller can populate fields but cannot inject free-form instructions
into a page the agent must read to function. The attack surface is bounded by the schema.

That is a genuinely novel security argument for open commerce networks, it is testable, and it
is India's to make. It has not, as far as this research can establish, been made.

**The honest counterweight:** ONDC's agentic story is currently aspiration, not specification.
Cumulative transactions passed 200 million by early 2026 and it is routinely named as the third
layer of an agentic DPI stack — but no formal ONDC agentic specification surfaced in this
research. The argument is available; the substrate is not yet ready.

### 5.3 What is actually live in India

- **Swiggy** — MCP across Food, Instamart and Dineout, reachable from ChatGPT, Claude and
  Gemini, 40,000+ products. **Cash on delivery only**: the payment leg does not exist. Gated
  behind ChatGPT developer mode with manual server registration, so it is a developer preview
  rather than a consumer product.
- **BigBasket** — the closed loop: catalogue search, prices, and **embedded UPI payment via
  Razorpay on Reserve Pay**, inside the chat session, with a single human confirmation.
- **Shopify UCP self-serve since 17 June 2026** — any developer can register an agent profile
  and call the public MCP endpoint with no approval gate. This is the lowest-friction agentic
  storefront path in the world right now, and it is available to Indian developers today.

The practical implication for anyone building: **the connectivity problem is largely solved and
was solved by the merchants, not by the payment industry.** What remains unsolved is everything
downstream of the cart.

---

## 6. Security architecture

### 6.1 The premise: injection is not solvable at the model layer

Indirect prompt injection has no reliable model-level defence, and there is no credible reason
to expect one — the model cannot distinguish instruction from data when both arrive as text in
the same channel, because that distinction is not a property of the text. Every product claim of
"we prevent prompt injection" should be read as a claim about detection rates, not prevention.

Therefore: **controls must be architectural, enforced outside the agent, by something the agent
cannot modify.** This is the same principle that makes OAuth necessary — an application's
declaration of its own scope was never the security boundary.

### 6.2 Layered architecture

**Layer 1 — Capability separation.** The component that reads untrusted content must not be the
component that holds spending authority. Concretely: a *quarantined* model processes web and
merchant content and may only emit structured, typed data — never instructions, never tool
calls. A *privileged* model never sees raw untrusted text, only the typed output. This is the
dual-LLM pattern, and it is the only known construction that bounds injection rather than
detecting it.

**Layer 2 — Provenance typing of context.** Every token entering the agent's context is tagged
with its origin: human turn, tool result, retrieved web content, memory. Any purchase intent is
then traceable to a provenance class. **An intent whose causal chain contains no human turn is
an injection candidate by construction, regardless of how legitimate it looks.**

This is the single most valuable idea in this section, because it converts the unsolvable
detection problem into a tractable dataflow problem — and it is the mechanism the thesis needs
in order to contribute more than an observation (§1.2).

**Layer 3 — Signed merchant responses.** Price, item identity and availability should arrive
signed by the merchant, so the value the agent acted on is non-repudiable at dispute time.
Neither AP2 nor UCP requires this today. It is a small protocol addition with a large
evidentiary payoff, and it is a natural UAP consultation proposal.

**Layer 4 — Out-of-process policy enforcement.** Limits live at the credential or the rail, not
inside the agent. Compromising the agent must not move the limit.

**Layer 5 — Out-of-band step-up, with one hard rule:**

> **A confirmation must never be delivered through the channel the instruction arrived on.**

If the agent asks "shall I confirm?" in the same chat window, an attacker who controls that
window answers yes. Confirmation must go to the device bound at mandate creation — in India,
the bank's UPI app, where the PIN already lives.

**Layer 6 — Endpoint authenticity.** The agent must verify the merchant is real. Humans use
visual trust cues; agents have none. On ONDC, network membership provides this natively — a
further argument for §5.2.

### 6.3 What no architecture can do

If an attacker fully controls the user's device, they control the UPI app, the chat session and
the confirmation channel. Nothing proposed here or elsewhere survives that. The honest framing
throughout should be: raise attacker cost, shrink the window of unnoticed abuse, bound the blast
radius. Never "prevention."

---

## 7. Trust architecture, and whether trust can be measured

### 7.1 Why consumers would delegate at all

Trust in this setting is not a feeling to be engineered but a **rational response to observed
reliability under known stakes**. Four levers, in order of power:

1. **Bounded downside** — the user must know the worst case before delegating, in rupees.
2. **Reversibility** — a strong undo is worth more than a strong prediction. This is why
   replenishment (returnable, low-value, repeated) will be trusted before travel (expensive,
   non-refundable, one-shot), regardless of which is technically harder.
3. **Graduated delegation** — earned autonomy: observe → recommend → execute-with-confirmation
   → execute-and-notify → execute-silently, with promotion tied to a measured record and
   automatic demotion on anomaly.
4. **Legible failure** — when it goes wrong the user must be able to see *why* and to attribute
   fault. Unattributable failure destroys trust disproportionately.

### 7.2 Explainability for the affected person, not the auditor

The person deciding whether to dispute is a consumer. An explanation that satisfies a model
audit — attention traces, tool logs, chain-of-thought — is not the artifact they need. The
consumer-facing explanation must answer three questions in one screen: *what did you think I
asked for; what did you consider; why this one.* No deployed system produces this. It is an
HCI contribution with a clear evaluation design.

### 7.3 Can trust be made measurable?

Yes, and this is a tractable paper. A proposed metric set, all instrumentable:

| Metric | Definition | Why it matters |
|---|---|---|
| **Intent fidelity rate** | Purchases the user affirms matched their intent, on post-hoc review | The direct measure; requires a labelled study |
| **Interruption precision** | Fraction of clarifying questions the user found worth being asked | Directly trades off against the next metric |
| **Silent error rate** | Wrong purchases that were *not* escalated | The number that actually destroys trust |
| **Provenance purity** | Fraction of executed intents whose causal chain contains a human turn | §6.2; the injection-exposure measure |
| **Reversal burden** | Time and steps to undo an unwanted purchase | Predicts trust better than accuracy does |
| **Drift disclosure rate** | How often the agent surfaces that it moved away from the stated intent | The §3 contribution, operationalised |
| **Delegation retention** | Whether users increase or reduce granted authority over time | The revealed-preference summary statistic |

`arXiv:2604.03976` (*Quantifying Trust: Financial Risk Management for Trustworthy AI Agents*)
is prior art here and should be read before claiming novelty on the metric framing.

---

## 8. Fraud analysis: substitution, not reduction

Does agentic payment reduce fraud? The intuitive answer is no. The correct answer is more
interesting: **it eliminates one entire class and imports another, and the two have different
scaling laws.**

### 8.1 What agents genuinely kill

| Fraud type | Why it stops working |
|---|---|
| **Phishing** | The agent has no psychology to exploit. It does not feel urgency, authority pressure, or fear of account closure |
| **Fake QR codes** | Visual deception targets human perception. An agent resolves an endpoint identifier, not an image |
| **Fake "collect" requests** | Depends on the human misreading pay-vs-receive. An agent parses the direction from the protocol field |
| **Social engineering / vishing** | Requires an improvising human under emotional pressure |
| **Typosquatting / lookalike domains** | Defeated by exact-match endpoint verification, which an agent can do perfectly and a human cannot |
| **Urgency and scarcity manipulation** | "Only 2 left!" has no purchase on a policy engine |

This is not a small list. It is most of India's current retail payment fraud by volume. An
agent that pays only registered endpoints under signed mandates is **structurally immune to the
entire deception-of-humans category.** That deserves to be stated plainly in the policy
conversation, because it is currently absent from it.

### 8.2 What replaces it

| New vector | Mechanism |
|---|---|
| **Indirect prompt injection** | Instructions hidden in pages, documents, reviews, retrieval results |
| **Answer-engine optimisation as attack** | Content optimised to be *found and believed* by agents rather than to be true |
| **Poisoned reviews and synthetic social proof** | Agents weight aggregate signals with no independent taste to override them |
| **Merchant-side reserve draining** | A hostile merchant pulls an entire block at once; Reserve Pay is built for multiple partial debits, so the pattern looks normal |
| **Refund manipulation** | Agents pushed into refunds where no failure occurred; generative media makes false evidence cheap |
| **Mandate-reference leakage** | The reference behaves as a bearer credential once it escapes |
| **Model-supply-chain attack** | The agent's model or orchestration platform is updated without the principal's knowledge |

### 8.3 The asymmetry that matters — and it is the section's real finding

> **Human-deception fraud scales linearly with victims. Machine-deception fraud scales with the
> agent population from a single artifact.**

A phishing campaign must deceive each victim separately; conversion rates are low and each
success costs the attacker effort. **One poisoned page that reliably injects one widely deployed
agent architecture reaches every user of that agent at once, at zero marginal cost.**

Fraud therefore shifts from **high-frequency, low-yield, human-targeted** to **low-frequency,
high-yield, infrastructure-targeted**. That has three consequences the industry has not priced:

1. **Fraud loss distributions become fat-tailed.** Actuarial models built on retail fraud
   frequency will systematically underestimate tail risk. This is an insurability problem before
   it is a security problem.
2. **Detection must move from the victim to the population.** Per-user anomaly detection cannot
   see a correlated attack that looks locally normal in every account. The right signal is
   *many agents suddenly behaving identically*.
3. **Homogeneity is systemic risk.** If most Indian shopping agents run on the same two or three
   foundation models with similar scaffolding, a single working injection is a systemic event.
   Model diversity becomes a prudential concern — the direct analogue of concentration risk in
   banking, and a strong policy contribution.

**Net verdict:** agentic payments are likely to *reduce fraud frequency* and *increase fraud
severity*, while moving the loss from consumers who can be socially engineered to institutions
that can be systematically exploited. Whether that is an improvement depends entirely on whether
the liability framework moves with it. It currently does not.

---

## 9. Regulatory implications

**The authentication collision, stated correctly.** RBI's Authentication Directions, 2025
require two factors with at least one dynamic per transaction, effective 1 April 2026, and move
from prescribed SMS OTP to principle-based authentication — explicitly permitting risk-based
approaches using contextual and behavioural signals. The exemption list includes recurring
transactions under the e-mandate framework. **Whether Reserve Pay-based agent debits fall inside
that exemption is the unresolved question**, and it determines whether agentic UPI is already
compliant or systematically non-compliant with full issuer liability under the compensation
provision. No published analysis addresses it. This is the single highest-value question in
Indian agentic payments policy right now.

**The permission hiding inside the same directions.** By naming contextual and behavioural
checks as acceptable authentication factors, RBI has already licensed the mechanism this domain
needs. A risk-based instruction-provenance score that triggers a real PIN challenge is not a
workaround — it is the approach the directions describe, applied to a transaction type nobody
has applied them to.

**FREE-AI.** RBI's framework requires model risk management and human oversight of autonomous
systems at banks, NBFCs and payment system providers. That converts per-decision agent evidence
from a nice-to-have into a compliance artifact with a budget attached.

**DPDP.** An agent that shops needs purchase history, budgets, location and preferences. Three
questions have no published answer from any Indian provider: what reaches the LLM, what stays
inside the PSP, what is shared with the merchant. Every section of this report creates a DPDP
obligation, and purpose limitation is genuinely hard when the purpose is "decide what I want."

**UDIR and the reason-code gap.** UPI disputes run through NPCI's UDIR with reason codes written
for failed, unauthorised or fraudulent *human* transactions. "The agent misunderstood my
instruction" maps to nothing. Notably, industry participants in the UAP consultation are
reportedly raising dispute and chargeback flows themselves — so this gap is recognised, and the
window to influence how it is closed is open now.

**The liability void.** A prompt-injected payment is *authorised but not intended*. The mandate
is valid, the credential is valid, nothing was compromised in the traditional sense — so it may
not qualify as an "unauthorised transaction" under RBI's customer protection framework at all,
meaning those protections may never attach. Combined with §8.3's fat tails, this is why no
insurance market can form: there is neither an actuarial base nor a defined loss event.

---

## 10. A reference architecture

Normative — what UAP should specify, and what a system should implement in the interim. Ordered
by how much each depends on protocol change.

**A. Consent artifact.** Model on the Account Aggregator consent artifact rather than inventing
a format: signed, machine-readable, purpose-coded, time-bounded, revocable, with a consent ID
and a mandatory audit log. Adopt AP2's mandate objects as the wire format where possible —
formats are commodities and AP2 is now under FIDO Alliance governance.

**B. Provenance-typed context (§6.2).** Every executed intent carries a provenance class. The
protocol requirement is minimal: a field asserting whether the intent traces to a human
conversational turn, and a signed attestation of that assertion from the agent platform.

**C. A verifier, specified.** The gap AP2 left open. Given a mandate and a proposed purchase,
some named party must evaluate scope fit, price delta against consent time, duplicate detection
across retries, cumulative draw, merchant authenticity, and provenance. **Specify who does this
and what they must record.** Today no protocol names the verifier.

**D. Process mandates (§3.5).** Where a purchase is drift-prone, the mandate should bind the
*decision procedure* — minimum options surfaced, disclosure of ranking basis, no undisclosed
paid placement — rather than only the outcome envelope.

**E. Graduated step-up, out-of-band.** Escalate on low provenance confidence or high drift, to
the device bound at mandate creation. Never in-channel.

**F. Decision record.** Append-only, signed, retaining: consent artifact and scope, price and
cart at consent time, agent identity and version, the options surfaced, the provenance class,
the verifier's decision and reason, and the debit outcome. **The options surfaced is the novel
field**, and §3.3 is why it belongs there.

**G. Dispute mapping.** New UDIR reason codes for agent-caused loss, distinguishing at minimum:
misread intent, drift beyond mandate, injected instruction, price drift, duplicate execution.
Without these, none of the above is actionable.

---

## 11. Research agenda, ranked

Scored on novelty × tractability × the availability of data a two-person team can actually get.

### Tier 1 — do these

**R1. Constructed preference vs. signed intent.**
*Claim:* mandate-scope verification is not a validity test, because the preference the purchase
is judged against does not exist at signing time and is partly caused by the agent's own
presentation.
*Novelty:* high — no bridging work found. *Tractability:* high — arguable analytically, testable
with a modest user study (same mandate, varied agent presentation, measure post-hoc affirmation).
*Venue shape:* CHI / CSCW, or a behavioural-economics-flavoured FAccT paper.
*Falsifier:* if post-hoc affirmation is insensitive to presentation order and choice-set
composition, the endogeneity claim fails.

**R2. Provenance-typed context as an injection control.**
*Claim:* tagging context by origin and requiring a human-turn ancestor for any payment intent
bounds injection where detection cannot.
*Novelty:* medium-high — the SoK names instruction-origin authentication as open; this is a
mechanism, not an observation. *Tractability:* high — implementable and measurable on public
injection benchmarks. *Venue:* a security venue. **This is the strongest thesis-project
candidate** because it produces a working artifact.

**R3. Is Reserve Pay inside RBI's e-mandate exemption?**
*Claim:* the compliance status of every agentic UPI debit in India is currently indeterminate.
*Novelty:* high — unaddressed publicly. *Tractability:* very high — it is a reading plus expert
interviews. *Venue:* a policy brief or the UAP consultation response, not a paper. **Highest
value per hour of any item here**, and it doubles as a door-opener into NPCI-adjacent rooms.

### Tier 2 — strong, more effort

**R4. Fraud substitution and the scaling asymmetry (§8.3).** Model fraud loss distributions
under agent homogeneity; argue model diversity as a prudential requirement. Novel policy
framing; needs data that may not exist yet.

**R5. Injection surface as a function of integration mode (§5).** Empirical: measure successful
injection rates across browser automation, MCP, and schema-constrained catalogue access.
**If the ONDC hypothesis holds, this is an India-specific security result with policy weight.**

**R6. Consumer-facing explanation for agent purchases (§7.2).** Design and evaluate the
three-question explanation artifact. Clean HCI contribution, straightforward evaluation.

### Tier 3 — real but crowded or blocked

**R7. When should an agent ask?** Cost-of-error framing for clarification. Genuinely open, but
sits inside a large, well-funded NLP literature and will be benchmarked against it.

**R8. Agent-aware dispute reason codes.** Valuable and unbuilt, but it is a standards
contribution rather than a research one, and it needs UDIR data access.

**R9. Legal personality and liability allocation.** Important, blocked on law rather than
engineering, and outside a technical team's competence.

### On positioning the thesis

The original prioritisation — *instruction origin verification and decision-time evidence* — is
sound, with one amendment: **origin verification is now a known-open problem, so the thesis must
deliver a mechanism (R2), not the diagnosis.** R1 is the more novel contribution and the more
interesting paper; R3 is the fastest to produce and the most useful politically. A defensible
project is R2 as the built artifact, R1 as the conceptual contribution, R3 as the policy chapter.

---

## Appendix — what to verify before external citation

1. **OC 228 pre-debit notification wording** — currently inferred, not read
2. **Whether Reserve Pay sits inside the e-mandate exemption** — the crux of §9
3. **₹10,000 per block vs per month** — sources conflict; all volume arithmetic depends on it
4. **`arXiv:2606.08790` (RAILS)** — adjacent to the verifier concept in §10C; read before
   claiming novelty
5. **`arXiv:2604.03976`** — read before claiming novelty on §7.3
6. **Whether ONDC has any agentic work underway** — nothing surfaced; ask ONDC directly
7. **Whether any live Indian agentic flow is human-absent** — every confirmed flow has a human
   confirmation step, which materially affects how urgent §3 currently is
