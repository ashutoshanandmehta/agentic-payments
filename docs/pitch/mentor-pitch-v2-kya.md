# Know Your Agent
## Financial identity, rules, and accountability for AI that spends money

**Final presentation — 29 July 2026**
[Your name] · [Program name]

> *Your bank knows you. Nobody knows your agents.*
> *We're the ID card, the rulebook, and the security camera for AI that spends money.*

---

## Slide 1 — Start with an analogy the room already understands

One person. One verified identity. **Multiple SIMs.**

Each SIM is cryptographically tied back to you. Each has its own number, its own plan,
its own limits. There's a cap on how many you can hold. You can kill any one of them
without touching the others. And every call any of them makes is attributable to you.

**Note what the SIM is actually for.** It isn't so you can work out afterwards who made a
call — you could often guess that from who was dialled. It's so the network can **decide, at
the moment of the call**, whether *this* line is allowed to make it; so you can give one line a
₹200 cap and another ₹2,000; and so you can cut off one line without cutting off the family.

**The SIM exists for the decision, not for the record.** Hold that distinction — it's the
answer to the hardest question in this deck.

**That is exactly what is about to happen to money.**

One person — or one company — with a verified identity, and **many agents** transacting
underneath it. Each with its own identity, its own limits, its own kill switch, and full
attribution back to the principal.

Nobody has built that yet.

---

## Slide 2 — What's actually breaking

AI agents have started spending money.

**Consumer:** booking travel, ordering groceries, paying bills.
**Business (already happening, today):** SaaS auto-renewals, ad-budget agents,
procurement bots, finance teams letting agents pay vendors.

But every money system ever built assumes the transactor is a **human**. So there is no
way to answer five questions:

| # | Question | Status today |
|---|---|---|
| 1 | **Which agent is this?** | No agent identity exists |
| 2 | **Whose agent is it?** | No chain to a verified principal |
| 3 | **What was it allowed to spend?** | Mandate lives in a prompt, not in the rail |
| 4 | **Is it behaving normally?** | Fraud models are trained on human patterns |
| 5 | **When it goes wrong, what's the proof?** | No dispute-grade record of instruction → action |

Question 4 deserves a beat: every fraud model in production scores *time-of-day, velocity,
device, geography*. An agent violates all four by design — it **is** 3 a.m. traffic at forty
calls a second with no device fingerprint. So today's models either block everything or
nothing.

And question 5 is the commercial blocker. A chargeback needs evidence. For an agent, the
evidence is *what it was instructed to do, what it actually did, and where the two diverged.*
No protocol currently specifies that record — **so no dispute is adjudicable, so no bank can
underwrite the risk, so banks will throttle agentic payments regardless of how good the
protocol is.**

**Critically, questions 1–3 must be answered *before* the payment, not after.** A limit is
enforced at authorization — the instant the payment is requested. Whatever the agent says it's
buying arrives *with* the request, from the requester, and you cannot use the spender's own
claim about itself to decide whether to permit the spend. **Attribution looks backwards.
Authorization has to look forwards.**

---

## Slide 3 — This has a name, and we got there on our own

Our design instinct was: *no more than N agents per user; limits derived from what the user
actually has; an agent can never be mandated beyond its principal's capacity.*

We later found the industry has a term for precisely this: **KYA — Know Your Agent.**
Identity that chains every agent cryptographically to a verified human or business principal,
with authority that can never exceed the principal's own.

Three independent confirmations that this is the live problem:

- **a16z** has written that agent identity and authentication become core infrastructure for
  the agent economy.
- **NPCI's UAP** (Unified Agentic Protocol, in drafting now) is specifying exactly these
  components: registration, verification, authorization, spending limits, audit trails.
- **Google's AP2** is building the cryptographic mandate-proof version globally; Visa,
  Mastercard, Amex and OpenAI+Stripe have each shipped their own agent-payment protocol.

The mental model in one phrase: **KYC, but for agents.** Agents as first-class financial
citizens with **derived, capped, verified** authority.

*This slide's job: we didn't read a trend report and pick a theme. We designed the primitive,
then found out the standards bodies are converging on it.*

---

## Slide 4 — What we build (and where the money lives)

**The user's money never moves. It stays in their existing bank account.**

We sit on top as a control layer:

```
        Company / User  ──(verified principal)
               │
     ┌─────────┴──────────┬──────────────┐
   Agent A             Agent B         Agent C
  (ad spend)         (procurement)    (SaaS renewals)
     │                   │                │
     ▼                   ▼                ▼
┌──────────────────────────────────────────────────┐
│                      K Y A                       │
│                                                  │
│ 1. AGENT IDENTITY                                │
│    Cryptographic ID chained to verified principal│
│    N-agent cap · scope · expiry · revocation     │
│                                                  │
│ 2. BOUND CREDENTIAL                              │
│    Virtual card / tokenized UPI handle           │
│    issued via partner bank or PA                 │
│    Rules baked into the credential itself        │
│                                                  │
│ 3. POLICY ENGINE                                 │
│    Deterministic mandate math.                   │
│    NO LLM in the approval path.                  │
│    Outside the mandate → payment does not happen │
│                                                  │
│ 4. BEHAVIORAL LAYER                              │
│    "Is this agent acting like itself?"            │
│    Anomaly → instant freeze                      │
│                                                  │
│ 5. TAMPER-EVIDENT AUDIT LOG                      │
│    Replayable: instruction → reasoning → action  │
│    → outcome. Every dispute has evidence.        │
└──────────────────────────────────────────────────┘
               │
   ┌───────────┼────────────┬──────────────┐
   ▼           ▼            ▼              ▼
UPI mandates  Cards    (later) stablecoin legs
        ── settlement details, beneath one mandate layer ──
```

**Say this line out loud on this slide:** *"Deterministic mandate math — no LLM in the
approval path."* A model must never be the thing that authorizes a payment; it can only
observe and flag. That distinction is what makes this auditable at all.

---

## Slide 5 — What we deliberately are NOT building

Our first version was: *every agent gets an account with us, and we approve the payments.*
**We killed it.** Three reasons, each independently fatal:

**1. License.** Holding funds and processing payments in India means a banking license —
RBI issues a couple a decade — or at minimum PPI/PA licenses plus a sponsor bank, crores
of capital, and years. Not a seed-stage path.

**2. Redundancy.** The money doesn't need a new home. The user's bank account plus UPI and
cards already store and move value perfectly well. What's missing isn't *accounts* — it's
**identity, mandate, and control for a new kind of transactor.** Per-agent sub-accounts are
better built as virtual accounts and tokenized credentials over the user's *real* account.

**3. Strategy.** NPCI will own agent **registration** on UPI rails. Competing with the
registry means fighting the utility — a fight nobody wins. The durable position is the
**intelligence NPCI won't build.** In their own words: they will not deploy inside banks'
environments, and rogue-agent control is *"the main concern we have to solve."*

**So we are not a bank, not a wallet, and not the registry. We are the verification and
control layer that sits above all three.**

*This slide's job: show we can kill our own idea for specific reasons. It's the most
credible slide in the deck.*

---

## Slide 6 — Timing: how we avoid betting on two futures

**The honest risk:** consumer agent-payment volume in India waits on **UAP shipping** *and*
**RBI approval** *and* **consumer adoption**. The pure consumer version is 12–24 months
early on revenue. That's a bet on two futures, and we're not taking it.

**The discipline: wedge on whoever transacts autonomously *today*.** Someone already does —
**businesses.**

### The wedge (revenue this year)
> **"Give your company's AI agents spend authority with real controls."**
> Per-agent virtual cards · mandates · anomaly alerts · audit logs

Who has this problem right now:
- Ad-spend agents moving real budget with no per-agent cap
- Procurement and vendor-payment bots
- SaaS auto-renewals nobody is watching
- Any finance team that has quietly let an agent touch a card

They have the pain, the budget, and a compliance deadline. They do **not** need UAP to exist.

**And this is a known category shape:** corporate cards + spend management is where Ramp
built a company worth tens of billions. **Agent-spend controls is that category's next
chapter** — same buyer, same budget line, new transactor.

### The maturation
The same identity + mandate + audit primitives become the **consumer UAP layer** the moment
the rail opens. The B2B business funds the wait and produces the behavioral data that makes
the consumer product good.

**One present. One protocol tailwind. Not two bets.**

---

## Slide 7 — Revenue model

We charge for **verification and control** — historically the thing interchange priced. But
in India we cannot rely on interchange, and we want to say that before you ask:

> **UPI P2M is zero-MDR by mandate.** There is no interchange to share on the UPI leg. Cards
> do carry interchange. So our revenue has to be **rail-independent** — priced as software and
> per-decision, with card interchange as upside rather than foundation.

**Four layers, deliberately sequenced:**

| Layer | What it is | Why it exists |
|---|---|---|
| **1. Platform fee** | Per agent, per month | Predictable, and it **grows as customers add agents** — expansion is automatic |
| **2. Decision fee** | Per authorization evaluated | Scales with volume, **works on zero-MDR rails**, mirrors how fraud/risk APIs price |
| **3. Interchange share** | On card-issued agent credentials | Real upside where cards are the rail. Not the foundation. |
| **4. Enterprise licence** | Banks, PSPs, agent platforms | Phase 2. Large ACV, long cycle, becomes the infrastructure business |

**Our two north-star metrics:**
- **AUM — Agents Under Mandate** (the compounding one)
- **MSV — Mandated Spend Volume** (the GMV equivalent)

**Pricing anchor: price against the loss, not against the software.** An ad-spend agent can
burn ₹5 lakh in a bad hour. A few thousand rupees a month of control is not a difficult
conversation.

**Two derived numbers to say out loud:**
- At ₹3,000 per agent per month, we cost **25–50 basis points of the spend we control.**
  Card interchange is 150–200 bps. **We're a fraction of interchange, on spend that has zero
  controls today.**
- A mid-size customer pays ₹25,000/month. **One prevented incident — a duplicated vendor
  payment, one runaway ad agent — covers 20 months of subscription.**

*(Full bottom-up derivation of every figure is in the appendix. Say once, early: "these are
hypotheses we're testing with design partners.")*

**What compounds:** behavioural baselines across agent traffic (nobody else will see agents at
scale, and that data improves with every customer), and becoming the **format** disputes are
adjudicated in. Rails underneath — UPI mandates, cards, later stablecoin legs — are
interchangeable settlement details. **The mandate layer is the product.**

---

## Slide 8 — Go to market

### The beachhead: performance marketing and ad-spend agents
Money already moves fast, automatically, in large amounts. Overspend is a **known, quantified**
pain with a number attached. The agent is already autonomous, and the buyer is sophisticated.
Then: **agencies** (spending *clients'* money — fiduciary pressure doubles), then **AI product
companies whose product transacts** (they need our controls to sell to their own enterprise
buyers, which converts them into our distribution).

### Who signs, and who feels the pain — they're different people
| Role | Relationship to us |
|---|---|
| **Engineering / platform lead** | Deployed the agents. Feels the risk first. **Our champion.** |
| **CFO / Financial Controller** | Owns the loss and the audit exposure. **Signs the cheque.** |
| **CISO / Compliance** | Can block us. Needs the threat model, not the demo. |

**The trigger we exploit: "shadow agent spend."** Engineering has already deployed agents that
touch money, and finance often doesn't fully know. We enter through engineering and create the
finance conversation.

### Trigger events — we hunt these, we don't spray
1. An **incident** — an agent overspent, double-paid, or bought the wrong thing
2. **Statutory audit** — the auditor asks for authorization evidence on agent payments
3. **Pre-launch** on a customer-facing agent that transacts
4. A **bank or partner asks** "what controls do you have?" before extending limits
5. **Board or investor diligence** on AI risk

### Channels, in order of when we turn them on
| # | Channel | Leverage |
|---|---|---|
| 1 | **Founder-led direct** to trigger-event companies | Low leverage, **highest learning.** This is how we earn the right to do #2 |
| 2 | **Agent platform / orchestrator partnerships** | **The scale channel.** One integration → many downstream customers |
| 3 | **Bank / PSP co-sell** | Highest ACV, longest cycle. Start relationships at month 3, expect revenue at 12–18 |
| 4 | **Auditors and CA firms** ⭐ | Underrated in India: arm auditors with an agent-payments control checklist and **they generate the demand** |
| 5 | **Developer-led free tier** (3 agents free, SDK) | Bottom-up land; finance expands it later |
| 6 | **Standards credibility** — the paper, iSPIRT, NPCI consultation | Not lead-gen. **Trust manufacturing** — it shortens every bank diligence cycle |

### The GTM risk we have to solve, said plainly
**The category doesn't exist, so the budget line doesn't exist.** Nobody has "agent spend
controls" in this year's plan.

**So we don't create a budget line — we borrow one.** We sell into *existing* budgets:
**spend management**, **fraud and risk**, or **audit and compliance**. Same money, already
approved, new problem.

---

## Slide 9 — How we got here: we evaluated three ideas

| | Idea | Verdict |
|---|---|---|
| **A** | **Real-time default risk** — monitor account irregularities to flag likely defaulters before the first missed EMI | Real pain. But it needs continuous account access from both borrower and institution (DPDP + AA consent friction), competes head-on with every bank's in-house risk team and existing bureau/AA analytics players, and we can't prove the model without lending data we don't have. **Long cycle, no wedge.** |
| **B** | **Insurance claim recovery** — most beneficiaries stop after the first rejection letter, though many claims are recoverable | Genuinely underserved and emotionally sharp. But it's a services business before it's a product, existing players occupy grievance redressal, and revenue depends on regulatory positioning we haven't validated. **Retained as fallback.** |
| **C** | **KYA — identity and control for agent spending** ✅ | **A problem that exists today (B2B), a standards body publicly asking for the answer, and no license required to start.** The only one of the three where being early is itself the moat. |

*We chose C because it's the only one where we can sell in 90 days **and** be positioned for
the protocol.*

---

## Slide 10 — Next 90 days

| Weeks | Milestone |
|---|---|
| 1–3 | **Working prototype.** Agent with a bound credential attempts a purchase outside its mandate → blocked, flagged, and replayable in the audit view. Demo on live infrastructure (UPI Circle delegation and/or a virtual-card sandbox). |
| 2–6 | **Partner-bank / PA conversation** for credential issuance. Confirm the no-license path in writing. |
| 4–8 | **Technical paper:** *"What UAP must get right about agent fraud and dispute evidence"* — threat model for agentic payments, why human-pattern fraud models fail on agent traffic, minimum contents of a dispute-grade agent audit trail. Circulate via iSPIRT, pi-labs network, IIT-K / C3iHub, and NPCI's consultation process. |
| 6–12 | **10 discovery calls with companies already running spending agents** → 2 design partners on a paid pilot. Goal is not revenue but **pricing discovery**: what they'd pay per agent, and which existing budget line it comes out of. |

**Success at 90 days:** a demo that blocks a rogue agent live, a written no-license path,
two paying design partners, and a paper circulating among the people writing the rules.

---

## Slide 11 — What we're asking you for

1. **Intros — two kinds.** (a) Any company you know running AI agents that touch spend
   (ads, procurement, finance ops) — those are our design partners. (b) Anyone in payments
   risk/fraud at a bank or PSP, or in the iSPIRT orbit.
2. **A hard review of the threat model** before we publish. We'd rather be corrected by you
   than by NPCI.
3. **One judgment call:** for the B2B wedge, is the sharper first customer the **company
   running the agents**, or the **platform selling the agents** (who could bundle us and give
   us distribution)? We can argue both and would take your read.

> *Your bank knows you. Nobody knows your agents.*
> *We're the ID card, the rulebook, and the security camera for AI that spends money.*

---
---

# Speaker script (~5 minutes)

> "One person. One identity. Multiple SIMs. Each SIM is tied back to you cryptographically,
> each has its own number and its own limits, there's a cap on how many you can hold, and you
> can kill any one of them without touching the others.
>
> And notice what the SIM is actually for. It's not so you can work out afterwards who made a
> call — you could usually guess that. It's so the network can decide, at the moment of the
> call, whether *this* line is allowed to make it. So you can cap one line at ₹200 and another
> at ₹2,000. And so you can cut off one line without cutting off the family. The SIM exists for
> the decision, not for the record.
>
> That's exactly what's about to happen to money. One person, or one company, with many
> agents transacting underneath them. And nobody has built it.
>
> Because AI agents have started spending money. Consumers — booking, ordering, paying bills.
> And inside companies, already, today — SaaS renewals, ad budgets, procurement bots, finance
> teams letting agents pay vendors.
>
> But every money system ever built assumes the transactor is a human. So there are five
> questions nobody can answer. Which agent is this. Whose agent is it. What was it allowed to
> spend. Is it behaving normally. And when it goes wrong, what's the proof.
>
> Two of those matter most. On behaviour: every fraud model in production scores time of day,
> velocity, device, location. An agent breaks all four by design — it *is* 3 a.m. traffic at
> forty calls a second. So the models block everything or nothing. And on proof: a chargeback
> needs evidence, and for an agent the evidence is what it was told, what it did, and where
> those diverged. No protocol specifies that record. Which means no dispute can be settled,
> which means banks can't underwrite the risk — so they'll throttle agent payments no matter
> how good the protocol is.
>
> Our design instinct was: cap the number of agents per user, derive their limits from what
> the user actually has, and never let an agent be mandated beyond its principal's capacity.
> It turns out the industry has a name for that. It's called KYA — Know Your Agent. a16z says
> agent identity becomes core infrastructure. NPCI's UAP draft specifies exactly these pieces:
> registration, verification, authorisation, limits, audit trails. Google's AP2 is building the
> cryptographic mandate version globally. So — KYC, but for agents.
>
> Here's what we build, and the important part is where the money lives: it doesn't move. It
> stays in the user's existing bank account. On top of it, every agent gets a cryptographic
> identity chained to a verified principal, with a cap, a scope, an expiry and a revocation.
> It gets a payment credential — a virtual card or a tokenised UPI handle through a partner
> bank — with the rules baked into the credential. Every attempted transaction passes through
> a policy engine doing deterministic mandate math. No LLM in the approval path — a model
> never authorises a payment, it only observes. Alongside it, a behavioural layer asking 'is
> this agent acting like itself,' and freezing it instantly if not. And everything lands in a
> tamper-evident log that can reconstruct any dispute.
>
> Now — what we're deliberately not building, because our first version was wrong. We
> originally said every agent gets an account with us and we approve the payments. We killed
> it for three reasons. License: holding funds in India means a banking licence, which RBI
> issues a couple of times a decade, or at minimum PPI and PA licences with a sponsor bank and
> crores of capital. Redundancy: the money doesn't need a new home — the user's bank plus UPI
> already move value fine. What's missing isn't accounts, it's identity and control for a new
> kind of transactor. And strategy: NPCI will own agent registration on UPI. Competing with
> the registry is fighting the utility. The durable position is the intelligence NPCI won't
> build — in their own words, they won't deploy inside banks' environments, and rogue-agent
> control is the main concern they have to solve. So we're not a bank, not a wallet, not the
> registry. We're the control layer above all three.
>
> On timing, let me be honest about the risk. Consumer agent payments in India need UAP to
> ship, RBI to approve, and consumers to adopt. That's a bet on two futures and we're not
> taking it. Instead we wedge on whoever transacts autonomously today — and that's businesses.
> Give your company's AI agents spend authority with real controls: per-agent virtual cards,
> mandates, anomaly alerts, audit logs. Those customers exist this year, they have budget, and
> they don't need UAP. And it's a known category — corporate cards and spend management is
> where Ramp built an enormous company. Agent-spend controls is that category's next chapter.
> Same buyer, same budget line, new transactor. And the same primitives become the consumer
> UAP layer the moment the rail opens.
>
> One present, one protocol tailwind — not two bets.
>
> On how we make money — and let me get ahead of the obvious objection. UPI is zero-MDR, so
> there's no interchange to share on the UPI leg. That means we can't be an interchange
> business in India. We price as software instead: a fee per agent per month, plus a fee per
> authorization decision we evaluate. Card interchange is upside where cards are the rail, not
> the foundation. The metric we care about is agents under mandate — because per-agent pricing
> means our revenue grows when a customer adds agents, and every customer adds agents.
>
> And we price against the loss, not against the software. At three thousand rupees per agent
> per month, we cost between twenty-five and fifty basis points of the spend we're controlling —
> card interchange is a hundred and fifty to two hundred. We're a fraction of interchange, on
> spend that has no controls at all today. Put differently: a mid-size customer pays twenty-five
> thousand a month, and one prevented incident covers twenty months of that.
>
> These are hypotheses, to be clear — we've derived them, not validated them. Testing the
> pricing is one of the ninety-day goals.
>
> On go-to-market: our beachhead is performance marketing and ad-spend agents, because the
> money already moves automatically and overspend is a pain with a number attached. Our
> champion is the engineer who deployed the agents — they feel the risk first. Our cheque
> comes from the CFO, who owns the loss and the audit exposure. We hunt trigger events: an
> incident, an audit question, a launch, or a bank asking what controls exist.
>
> And the honest GTM problem: this category doesn't exist, so the budget line doesn't exist.
> So we don't create a budget line — we borrow one. We sell into spend management, fraud and
> risk, or audit and compliance. Same money, already approved, new problem.
>
> We looked seriously at two other ideas: early-warning default risk for lenders, and helping
> insurance beneficiaries recover rejected claims. Both are real. We chose this one because
> it's the only one where we can sell in ninety days *and* be positioned for the protocol.
>
> What we'd like from you: intros to any company running agents that touch spend, a hard
> review of our threat model before we publish it, and your read on one call — is our first
> customer the company running the agents, or the platform selling them?
>
> Your bank knows you. Nobody knows your agents. We want to be the ID card, the rulebook, and
> the security camera for AI that spends money."

---
---

# Q&A — prepared answers

**"Do you need a license?"**
Not in the wedge, and that's deliberate. We never hold or move funds. Credentials are issued
by a partner bank or payment aggregator; we're the identity, policy and audit layer on top.
Confirming that path in writing is a 90-day milestone, not an assumption.

**"Why won't NPCI just build this?"**
They're building the registry and the protocol — the utility. They've said publicly they
won't deploy inside banks' environments, and that rogue-agent control is their unsolved
problem. That's the same split as UPI itself: NPCI built the rail, and a layer of companies
built the risk, reconciliation and control products on top.

**"Why won't Ramp / Volopay / an existing spend-management player add this?"**
They're built for *human* expense workflows — approvals, receipts, reimbursements. Agent
identity chained to a principal, cryptographic mandates enforced pre-authorisation, and
behavioural baselines for non-human traffic are different primitives, not a feature toggle.
Realistically they're a distribution partner or an acquirer, and either is a fine outcome.

**"Why won't the banks build it themselves?"**
Some will try, and they'll each build it once, for themselves, badly, in 18 months. A neutral
third-party audit trail is also more credible in a dispute than one written by a party to it.

**"Isn't this just fraud detection?"**
Fraud detection asks *"does this look like this human?"* We ask *"did this agent stay inside
its granted authority, and can we prove what happened?"* The second question is new, and it's
the one blocking launches.

---

### ⚠️ **"The transaction already records what it was paid for — can't you just tell from that which agent did it?"**

**This is the hardest question in the deck. Concede the true part immediately.**

**Where the objection is right:** if you run one grocery agent and one ad-spend agent, the
merchant name usually *does* tell you which one transacted. And your own application logs
already record which agent called which API. So for benign, non-overlapping activity, you can
often infer attribution without agent identity. **Say this out loud.** Claiming otherwise is
false and a sharp mentor will catch it.

**Why it doesn't survive: attribution was never the point.** Five things a reason field cannot
do —

**1. The rail has to decide before it knows the reason.**
A limit is enforced at authorization, the moment the payment is requested. The reason arrives
*with* the request, from the requester. You cannot use the spender's own claim about itself to
decide whether to permit the spend. Enforcement needs a subject that already exists and is
already scoped. *Attribution is forensics. Authorization is prevention.*

**2. Knowing who did it doesn't let you stop them.**
Even with perfect attribution, one shared credential gives you exactly one lever: kill the
credential — and break all five agents. You cannot suspend agent B while A, C, D and E keep
working. **Knowledge is not control.**

**3. One credential is one limit.**
Five agents on a shared card share a shared pool. The ads agent can quietly consume the
procurement budget. Reason fields don't partition a limit; separate credentials do.

**4. The memo is written by the party under suspicion.**
Merchant name and category come from the acquirer and are reasonably trustworthy. But *intent*
— what this payment was for, what the agent was trying to achieve — is **self-reported by the
agent.** A compromised or prompt-injected agent writes whatever memo makes it look legitimate.
Self-reported intent is a claim, not evidence. And mandates are about intent.

**5. The bank and the merchant cannot see your logs.**
Your internal record of *"Agent B did this"* never leaves your infrastructure. To the bank
underwriting the risk, and the merchant deciding whether to accept the traffic, all five agents
are one indistinguishable actor. And if the agent isn't yours — third-party, running on someone
else's platform — you don't have the logs at all.

**Also: inference degrades exactly when you need it most.** It works for two agents doing
obviously different things. It fails for a fleet of fifty agents doing the *same* thing, for
two procurement agents with overlapping vendors, and for any agent behaving abnormally — which
is precisely the case you built the system for.

**The analogy to use if pressed:** five employees sharing one office keycard. The log says the
server room was opened at 2 a.m., and you might well guess who from the roster. You still
cannot revoke just that person, still cannot grant one of them server-room access and not
another, and **the door has to decide whether to open before anyone explains why they're
there.**

> **One line to memorise: the ID isn't for the statement. It's for the decision.**

---

### **"Per-agent virtual cards already exist. Isn't the card just a commodity?"**

**Yes — and be the first to say it.** Per-employee and per-vendor virtual cards are already
available from several issuers. The card is our **enforcement mechanism, not our moat.**

What does *not* exist today:
- a verified cryptographic chain from agent → principal (N-agent cap, authority derived from the
  principal's real capacity)
- mandate semantics — scope, expiry, instant revocation — enforced **pre-authorization**
- behavioural baselines for **non-human** traffic
- a dispute-grade audit format that reconstructs instruction → action

We use commodity rails **on purpose**: it's why we need no licence and can ship in weeks. The
product is the identity, the mandate and the evidence — not the plastic.

**"What's actually defensible in 3 years?"**
Two things. Behavioural baselines across agent traffic — nobody else will see agents at
scale, and that data compounds. And becoming the **format** agent disputes are adjudicated
in; standards are sticky in a way features aren't.

**"What have you built so far?"**
Be straight: *"Nothing shipped — the prototype is the next three weeks. What we have is the
threat model, the architecture, and a wedge we deliberately picked because it needs no licence
and no protocol. We also killed our own first version, and slide 5 is why."* A clean "not
yet" with a specific plan beats a vague "we're working on it."

**"What if UAP takes three years?"**
Then the B2B business is unaffected — those agents are spending now, on cards, with no
controls. UAP is upside on timing, not a dependency.

**"How big can this get?"**
Frame it as a take-rate on agent-initiated spend. Don't quote a TAM number you haven't built
bottom-up — say *"we'd rather show you the two design partners first."* Refusing to invent a
number is a credibility gain in front of most mentors.

**"What exactly is your pricing?"**
*"A hypothesis, not a decision — validating it is a 90-day goal."* Then give it: roughly
₹3,000 per agent per month with a floor around ₹25,000/month, plus a per-decision fee on
volume, free up to three agents to get engineers in. And name the anchor: we price against the
loss, not the software. **Saying "hypothesis" costs nothing and protects you from a mentor who
knows the market better than you do.**

**"How do you get the first ten customers with no brand?"**
Trigger events, not outbound spray. Companies that just had an agent overspend, companies
mid-audit being asked for payment authorization evidence, and companies about to launch a
transacting agent. We reach them founder-to-founder through the program network, pi-labs, and
IIT-K — and we enter through the engineer who deployed the agents, not through procurement.

**"What if your platform partner just builds this themselves?"**
Likely, eventually, for their biggest accounts — which is why direct sales come first. Direct
customers give us the threat model, the incident data and the behavioural baselines that a
platform can't replicate from a standing start. And if a platform would rather buy than build,
that's an acquisition, which is a fine outcome for a seed-stage company.

**"Why not just go straight to the banks — bigger cheques?"**
Because a bank's first question is *"who else uses this?"* An 18-month cycle with no
references is how seed companies die. B2B customers fund the wait and produce the references.

---
---

# Appendix — the numbers, built bottom-up

*Every figure here is a **hypothesis to be tested with design partners**, not a validated
model. But each one is **derived**, not picked — so when a mentor pushes on a number, you can
show the assumption underneath it. That is the whole point of this appendix.*

---

## Step 1 — The pricing structure

| Tier | Who | Price |
|---|---|---|
| **Free** | Developers, ≤3 agents | ₹0 — capped decisions, no SLA. Land motion only. |
| **Growth** | 3–25 agents | **₹3,000 / agent / month**, floor **₹25,000 / month** |
| **Scale** | 25+ agents | First 25 at ₹3,000, **each agent beyond 25 at ₹1,500** + **₹1 per decision** beyond included volume |
| **Enterprise** | Banks, PSPs, agent platforms | Annual licence **₹75L–2Cr** + per-decision |

*Note the Scale tier is a volume **band**, not a flat rate — a 25-agent customer never pays
less than a 24-agent one.*

---

## Step 2 — Derive ACV from real customer shapes

| | **A. Mid-size D2C brand** | **B. Performance agency** | **C. AI product co. (fleet)** |
|---|---|---|---|
| Agents | 8 | 25 | 50 |
| Agent-initiated spend / month | ₹50L | ₹3Cr (client money) | varies |
| Payment authorizations / month | ~240 | ~750 | ~5,000 |
| **Monthly price** | 8 × ₹3,000 = ₹24,000 → **₹25,000 floor** | 25 × ₹3,000 = **₹75,000** | 25×₹3,000 + 25×₹1,500 = **₹1,12,500** |
| **ACV** | **₹3.0L** | **₹9.0L** | **₹13.5L** + decisions |
| **Cost as % of spend controlled** | **0.50%** (50 bps) | **0.25%** (25 bps) | — |

### The two derived numbers that win the pricing argument

**1. We cost 25–50 basis points of the spend we control.** Card interchange is 150–200 bps.
**We are a fraction of interchange, on spend that currently has zero controls.**

**2. One prevented incident pays for years.** Archetype A pays ₹25,000/month. A single
duplicated vendor payment or a runaway ad agent burning ₹5L covers **20 months** of the
subscription. That's the whole sales conversation.

**Blended Phase-1 ACV: ₹4L** — mix skewed to archetype A, with design-partner discounts.

---

## Step 3 — Derive customer count from the actual funnel

**Phase 1 assumptions (months 3–9, two founders selling part-time while building):**

| Step | Rate | Result |
|---|---|---|
| Discovery calls | 10 / month × 6 months | **60 calls** |
| Qualified — hit a real trigger event | 30% | **18 qualified** |
| Closed — new category, no brand, no references | 30% | **5–6 closed** |
| Free-tier / inbound conversions | — | **+2** |
| | | **≈ 8 paying customers by month 9** |

> **Note:** an earlier draft said 12. The funnel doesn't support 12 with two part-time
> founders and no references. **8 is the honest number** — and being visibly conservative here
> buys credibility for every other figure in the deck.

---

## Step 4 — The ARR build

| Phase | Months | Build | ARR |
|---|---|---|---|
| **0 — Design partners** | 0–3 | 10 discovery calls → 2 partners. Validate threat model, ship prototype, discover pricing. | **~₹0**, deliberately |
| **1 — Founder-led direct** | 3–9 | 8 customers × ₹4L | **≈ ₹32L** |
| **2 — Leverage** | 9–18 | 26 customers × ₹6L = ₹1.56Cr<br>+ 1 platform partnership ≈ ₹60L<br>+ 1 bank/PSP **pilot** ≈ ₹25L | **≈ ₹2.4Cr** |
| **3 — Infrastructure** | 18–30 | 60 customers × ₹7L = ₹4.2Cr<br>+ 2–3 platform deals ≈ ₹2Cr<br>+ 1–2 bank licences ≈ ₹1.5Cr | **≈ ₹7.7Cr** |

**Phase 2 customer math:** 22 new customers over 9 months (~2.5/month, now with references),
minus ~15% logo churn → **26 net**. ACV rises ₹4L → ₹6L from better mix plus agent-count
expansion, not price increases.

**Phase 3 lands at ≈₹7.7Cr ARR (~$900K) at month 30 — Series-A shaped, and none of it requires
UAP to have shipped.** UAP is upside on timing, not a dependency.

---

## Step 5 — Unit economics, derived

### CAC (founder-led)
| Input | Value |
|---|---|
| Calls to close one customer | ~20 (incl. 7 qualified conversations) |
| Founder hours incl. prep and follow-up | ~40 hrs |
| Notional founder time cost @ ₹1,500/hr | ₹60,000 |
| Travel, tools, collateral | ₹15,000 |
| **CAC** | **≈ ₹75,000** |

### Payback and LTV
- Gross profit per customer = ₹4L ACV × 85% GM = **₹3.4L/year** = ₹28,300/month
- **CAC payback = ₹75,000 ÷ ₹28,300 = 2.7 months**
- LTV over 3 years with expansion ≈ **₹11L** → **LTV/CAC ≈ 14×**

> **Say this caveat before the mentor does:** 14× is flattered by costing founder time at
> ₹1,500/hr. **When we hire a sales team, CAC rises 3–5× and LTV/CAC lands nearer 3–4×** —
> which is still healthy, and is the number we actually plan against.

### Gross margin build (per ₹100 of software revenue)
| Line | ₹ |
|---|---|
| Cloud + infra (policy engine, audit log) | −8 |
| Support and success | −7 |
| **Gross margin — software** | **85%** |
| Gross margin — card interchange line | **30–50%** (sponsor bank keeps most) |
| **Blended once card revenue exists** | **~75–80%** |

### NRR build
- Agent count per customer: 8 → 12 in year two (**+50%**)
- Revenue effect, dampened by tier floors: **+35%**
- Revenue churn: **−12%**
- **NRR ≈ 120%**, driven **entirely by agent proliferation** — we don't need price rises to grow

---

## Step 6 — Market size, bottom-up (and the honest conclusion)

**Filter:** Indian companies with ≥₹25L/month of automated or agent-initiated spend.

| Segment | Companies |
|---|---|
| D2C brands with meaningful ad spend | ~6,000 |
| Performance / media agencies | ~2,000 |
| Tech and SaaS cos with procurement automation | ~3,000 |
| AI product companies whose product transacts | ~500 (growing fastest) |
| **Serviceable near-term** | **≈ 10,000** |

- Direct motion: 10,000 × ₹5L ACV = **₹500Cr (~$60M)**
- Bank/PSP licences: ~40 banks + ~20 PSPs × ₹1Cr = **₹60Cr**
- **India SAM ≈ ₹560Cr (~$65M)**

### What that number actually tells you — say this out loud
**₹560Cr is a beachhead, not a prize.** The direct India B2B market alone does not build a
large company.

The prize is two things it leads to: **being the mandate layer when consumer agent volume
arrives on UAP rails** (orders of magnitude more transactions), and the fact that **the product
is protocol-shaped, so it exports** — AP2, Visa and Mastercard agent protocols create the same
gap in every market.

*Volunteering that your own SAM is small is counter-intuitive, and it's exactly the kind of
honesty that makes a mentor trust the rest of your numbers.*

---

## Honest risks in this model

| Risk | Our answer |
|---|---|
| **Zero-MDR on UPI** kills per-transaction economics on India's biggest rail | Price as software + per-decision. Interchange is upside, never foundation. |
| **Per-decision revenue is immaterial in Phase 1** — 240 decisions × ₹1 = ₹240/month | Correct, and we say so. Phase 1 is ~100% platform fee. Decision pricing only matters at fleet scale (archetype C), and it's there because it's **rail-independent**, not because it pays early. |
| **No budget line exists** for this category | Borrow an existing one — spend management, fraud/risk, or audit/compliance |
| **Bank cycles are 12–18 months** | Direct B2B funds the wait; banks are Phase 2 by design |
| **CAC rises sharply** once founders stop selling | Modelled: LTV/CAC 14× → 3–4×. Plan against the lower one. |
| **Platform partners may build it** | Direct-first for the data and references they'd need; acquisition is an acceptable outcome |
| **Per-agent pricing might discourage adding agents** — killing our own NRR engine | Watch it explicitly in design partners. Fall back to decision-based pricing if agent counts stall. |

**One number to verify before you say it:** UPI P2M zero-MDR is government-mandated, but
credit-card-on-UPI does carry interchange above a threshold, and these rules have changed
before. Check the current position rather than describing it from memory — being wrong on MDR
in front of a fintech mentor is expensive.

---
---

# Pre-flight: check these before you present

1. **Soften anything you can't source.** Say *"NPCI has begun work on a unified agentic
   protocol, publicly described as in consultation with industry"* — don't quote spec
   sections or dates. Same for the a16z reference: *"a16z has written about agent identity
   becoming core infrastructure"* is safe; a specific claim from a specific post is not
   unless you've read it. **Confidence about the problem, humility about the spec status.**

2. **The Ramp valuation.** Only say a specific figure if you've verified it that morning —
   otherwise *"a company worth tens of billions"* makes the same point and can't be corrected
   from the floor. One wrong number invites the mentor to doubt the rest.

3. **Slides 5 and 6 are the ones that win the room** — killing your own idea for three
   specific reasons, and refusing a two-futures bet in favour of a customer who exists today.
   If you're running short on time, cut Slide 9. Never cut 5 or 6.

4. **Rehearse the ⚠️ question in Q&A until it's automatic** — *"can't you just tell which agent
   it was from what it bought?"* It's the one question that can unravel the pitch, because the
   obvious answer (attribution) is genuinely weak. The winning move is to concede that inference
   often works, then pivot: **the ID is for the decision, not the record.** A limit has to be
   enforced before the payment, using something the spender can't self-report. Concede fast,
   pivot hard — that exchange will impress your mentor more than any slide.

5. **Raise the zero-MDR constraint yourself on Slide 7** — don't let a fintech mentor raise it
   for you. Saying *"we can't be an interchange business in India, so we price as software"*
   turns the single biggest hole in the revenue model into evidence that you understand the
   market. Verify the current MDR position before you say it.

6. **Label every number a hypothesis.** Slides 7–8 and the appendix contain guesses. Say so
   once, early — *"these are hypotheses we're testing with design partners"* — and you can then
   be specific without being exposed.

*(Name note: "KYA" works as the category, but it's a category not a brand. If you want a
product name for the title slide, pick one that sounds like infrastructure rather than
security theatre — but don't spend today's remaining time on it.)*
