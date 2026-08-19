# Unified Agentic Protocol


# SLIDE 1 — TITLE
**Runtime: 20 sec**

### On-slide
> # Beyond UPI
> ### : Securing the Next Generation of AI-Powered Payments
*Footer:* Ashutosh Anand · BS-MS, Y22

### Visual
Title slide. If your template allows one big pull-quote, use:
**"Your bank knows you. Nobody knows your agents."**

### Speaker notes
Don't read the slide. Open cold with the analogy on slide 2.

---

# SLIDE 2 — THE ANALOGY
**Runtime: 60 sec**

### On-slide
> ## One identity. Many SIMs.
>
> - One person, one verified identity
> - Each SIM: own number, own limit
> - A cap on how many you can hold
> - Kill one without killing the family
> - **The network decides at the moment of the call**

**Kicker (largest text on slide):**
**The SIM exists for the decision, not the record.**

### Visual
One person icon at top → four SIM cards fanned below, each labelled a *different* rupee limit
(₹200 / ₹500 / ₹2,000 / ₹5,000). One card greyed out and struck through, to show selective
revocation.

### Speaker notes
"One person, one identity, multiple SIMs. Each tied back to you, each with its own number and
its own limit, a cap on how many you can hold, and you can kill any one without touching the
others.

Now notice what the SIM is actually *for*. It's not so you can work out afterwards who made a
call — you could usually guess that. It's so the network can decide, **at the moment of the
call**, whether *this* line is allowed to make it. So you can cap one line at ₹200 and another
at ₹2,000. And so you can cut off one line without cutting off the family.

That's exactly what's about to happen to money. One person, or one company, with many agents
transacting underneath them. And nobody has built it."

---

# SLIDE 3 — THE PROBLEM
**Runtime: 90 sec**

### On-slide
> ## Money systems only know how to trust humans
>
> **Five questions nobody can answer about an agent:**
>
> 1. Which agent is this?
> 2. Whose agent is it?
> 3. What was it allowed to spend?
> 4. Is it behaving normally?
> 5. When it goes wrong, what's the proof?

**Kicker:** **Questions 1–3 must be answered *before* the payment.**

### Visual
Five numbered rows, each with a red ✗ in the "answerable today" column. Keep the ✗ column
visually loud — the emptiness *is* the argument.

### Speaker notes
"AI agents have started spending money. Consumers — booking, ordering, paying bills. And inside
companies already today — SaaS renewals, ad budgets, procurement bots, finance teams letting
agents pay vendors.

But every money system ever built assumes the transactor is a human. So there are five
questions nobody can answer.

Two matter most. On behaviour — every fraud model in production scores time of day, velocity,
device, location. An agent breaks all four by design; it *is* 3 a.m. traffic at forty calls a
second. So the models block everything or nothing.

And on proof — a chargeback needs evidence, and for an agent the evidence is what it was told,
what it did, and where those diverged. No protocol specifies that record. So no dispute can be
settled, so banks can't underwrite the risk — and they'll throttle agent payments no matter how
good the protocol is.

One thing to notice: the first three have to be answered *before* the payment, not after. A
limit is enforced at authorisation."

---

# SLIDE 4 — THE CATEGORY
**Runtime: 60 sec**

### On-slide
> ## This has a name: KYA
> ### Know Your Agent — KYC, but for agents
>
> **Our design instinct:** cap agents per user · derive limits from the principal's real capacity · an agent can never exceed its principal
>
> - **NPCI UAP** — registration, verification, limits, audit trails
> - **Google AP2** — cryptographic mandate proofs
> - **Visa** — *Trusted Agent* · Mastercard · Amex · OpenAI + Stripe
> - **a16z** — agent identity becomes core infrastructure

### Visual
Left: your three design rules. Right: the four external confirmations. A large arrow between
them labelled **"we got here first, then found the name."** Logo row along the bottom.

### Speaker notes
"Our instinct was: cap the number of agents per user, derive their limits from what the user
actually has, and never let an agent be mandated beyond its principal's capacity.

It turns out the industry has a name for that — KYA, Know Your Agent. NPCI's UAP draft
specifies exactly these pieces. Google's AP2 is building the cryptographic mandate version
globally. Visa's is literally called Trusted Agent.

So: KYC, but for agents."

**Emphasise the ordering.** *We designed the primitive, then discovered the standards bodies
were converging on it* lands completely differently from *we read that KYA is hot.*

---

# SLIDE 5 — THE PRODUCT
**Runtime: 90 sec**

### On-slide
> ## The money never moves
> ### Five primitives on top of the account the user already has
>
> 1. **Agent identity** — chained to a verified principal
> 2. **Bound credential** — virtual card / tokenised UPI handle
> 3. **Policy engine** — deterministic. No LLM in the approval path.
> 4. **Behavioural layer** — is this agent acting like itself?
> 5. **Audit log** — tamper-evident, replayable

**Kicker:** **Enforced at the credential, not inside the agent — so compromising the agent doesn't move the limit.**

### Visual
Vertical stack, top to bottom:
`Principal` → three `Agent` boxes side by side → one wide **KYA** band containing the five
numbered primitives → bottom row of rails: `UPI mandates` `Cards` `Stablecoin (later)`
labelled *"settlement details."*

### Speaker notes
"The important part first: the money doesn't move. It stays in the user's existing bank account.

On top, every agent gets a cryptographic identity chained to a verified principal, with a cap,
a scope, an expiry and a revocation. It gets a payment credential — a virtual card or tokenised
UPI handle through a partner bank — with the rules baked into the credential itself. Every
attempted transaction passes a policy engine doing deterministic mandate math. **No LLM in the
approval path** — a model never authorises a payment, it only observes and flags. Alongside it,
a behavioural layer asking 'is this agent acting like itself,' freezing it instantly if not.
And everything lands in a tamper-evident log that reconstructs any dispute.

The line that matters: the mandate is enforced at the credential, not inside the agent. So if
someone prompt-injects the agent, the limit doesn't move."

---

# SLIDE 6 — WHAT WE KILLED
**Runtime: 75 sec**

### On-slide
> ## Our first version was wrong
> ### Three reasons, each independently fatal
>
> - **Licence** — holding funds means a banking or PPI/PA licence, crores, years
> - **Redundancy** — the money doesn't need a new home
> - **Strategy** — NPCI will own the registry. Don't fight the utility.

**Kicker:** **Not a bank. Not a wallet. Not the registry.**

### Visual
Three boxes with heavy strike-throughs, then one clean box below labelled
**"The control layer above all three."**

### Speaker notes
"We originally said: every agent gets an account with us and we approve the payments. We killed
it, for three reasons.

Licence — holding funds in India means a banking licence, which RBI issues a couple of times a
decade, or at minimum PPI and PA licences with a sponsor bank and crores of capital.

Redundancy — the money doesn't need a new home. The user's bank plus UPI already move value
fine. What's missing isn't accounts, it's identity and control for a new kind of transactor.

Strategy — NPCI will own agent registration on UPI. Competing with the registry means fighting
the utility. The durable position is the intelligence NPCI won't build. In their own words:
they won't deploy inside banks' environments, and rogue-agent control is the main concern they
have to solve.

So we're not a bank, not a wallet, not the registry. We're the control layer above all three."

**This is the slide that wins the room.** Don't rush it.

---

# SLIDE 7 — TIMING & WEDGE
**Runtime: 90 sec**

### On-slide
> ## One present, not two futures
>
> **Consumer needs three things:** UAP ships → RBI approves → consumers adopt
> **= 12–24 months early on revenue**
>
> **Businesses transact autonomously today:**
> - Ad-spend agents
> - Procurement and vendor-payment bots
> - SaaS auto-renewals
> - Finance teams letting agents pay
>
> → *"Give your company's AI agents spend authority with real controls."*

**Kicker:** **Same primitives become the consumer UAP layer when the rail opens.**

### Visual
Two horizontal timelines. Top: "Consumer" with three sequential gates, revenue starting far
right. Bottom: "Business" with revenue starting now. Make the contrast the whole visual.

### Speaker notes
"Let me be honest about the risk. Consumer agent payments in India need UAP to ship, RBI to
approve, and consumers to adopt. That's a bet on two futures and we're not taking it.

So we wedge on whoever transacts autonomously today — businesses. Per-agent virtual cards,
mandates, anomaly alerts, audit logs. Those customers exist this year, they have budget, and
they don't need UAP.

And it's a known category shape. Corporate cards plus spend management is where Ramp built an
enormous company. Agent-spend controls is that category's next chapter — same buyer, same
budget line, new transactor.

The same primitives become the consumer layer the moment the rail opens. One present, one
protocol tailwind — not two bets."

---

# SLIDE 8 — REVENUE MODEL
**Runtime: 75 sec**

### On-slide
> ## How we make money
> ### UPI is zero-MDR — so we price as software, not interchange
>
> | Layer | Price |
> |---|---|
> | Platform fee | ₹3,000 / agent / month |
> | Decision fee | ₹1 per authorization *(rail-independent)* |
> | Interchange share | Card legs only — **upside, not foundation** |
> | Enterprise licence | Banks · PSPs · agent platforms |

**Kicker (make this the biggest thing on the slide):**
**25–50 bps of the spend we control. Interchange is 150–200 bps.**

### Visual
Two horizontal bars side by side: **Us 25–50 bps** vs **Interchange 150–200 bps**. The length
difference does the work. Below, small: *Metrics — Agents Under Mandate · Mandated Spend Volume.*

### Speaker notes
"Let me get ahead of the obvious objection. UPI is zero-MDR, so there's no interchange to share
on the UPI leg. We can't be an interchange business in India. So we price as software: a fee
per agent per month, plus a fee per authorisation decision we evaluate. Card interchange is
upside where cards are the rail, not the foundation.

We price against the loss, not the software. At ₹3,000 per agent per month we cost twenty-five
to fifty basis points of the spend we're controlling — interchange is a hundred and fifty to
two hundred. A fraction of interchange, on spend that has no controls at all. Put differently:
a mid-size customer pays ₹25,000 a month, and one prevented incident covers twenty months of
that.

The metric we care about is agents under mandate, because per-agent pricing means our revenue
grows every time a customer adds an agent — and every customer adds agents.

To be clear, these are hypotheses. Derived, not validated. Testing the pricing is a 90-day
goal."

**Raise zero-MDR yourself.** Letting a fintech mentor raise it costs you the slide.

---

# SLIDE 9 — GO TO MARKET
**Runtime: 90 sec**

### On-slide
> ## Enter through the engineer. Get paid by the CFO.
>
> **Beachhead:** performance marketing & ad-spend agents
>
> | | |
> |---|---|
> | **Champion** | Engineer who deployed the agents — feels the risk first |
> | **Buyer** | CFO — owns the loss and the audit exposure |
> | **Blocker** | CISO — needs the threat model, not the demo |
>
> **Triggers we hunt:** an incident · statutory audit · pre-launch · a bank asking "what controls?"
>
> **Scale channel:** agent platform partnerships — one integration, many customers
> **India edge:** arm auditors with a control checklist → *they* create demand

**Kicker:** **No budget line exists for this. So we borrow one — spend management, fraud, or audit.**

### Visual
Left half: persona split (engineer → CFO, with CISO as a gate). Right half: the six channels as
a numbered list with "turn on at month X" labels.

### Speaker notes
"Our beachhead is performance marketing and ad-spend agents — the money already moves
automatically, budgets are large, and overspend is a pain with a number attached.

Our champion and our cheque are different people. The engineer who deployed the agents feels
the risk first; the CFO owns the loss and signs. The wedge is *shadow agent spend* — engineering
has already deployed agents touching money and finance often doesn't fully know. We enter
through engineering and create the finance conversation.

We hunt trigger events rather than spraying outbound: an incident, an audit question, a launch,
or a bank asking what controls exist.

Two channels worth naming. Agent platform partnerships are the scale channel — one integration,
many downstream customers — but we have to earn it with direct sales first, because a platform
buys the threat model and incident data. And an India-specific one: arm auditors with an
agent-payments control checklist and they generate demand for us.

And the honest problem: this category doesn't exist, so the budget line doesn't exist. So we
don't create one — we borrow one. Spend management, fraud and risk, or audit and compliance.
Same money, already approved, new problem."

---

# SLIDE 10 — WHY THIS ONE
**Runtime: 60 sec**

### On-slide
> ## We evaluated three ideas
>
> | | Idea | Verdict |
> |---|---|---|
> | **A** | Real-time default risk for lenders | Consent friction, competes with in-house risk teams, no data to prove the model |
> | **B** | Insurance claim recovery | Real pain — but services-first, and regulatory position unvalidated. **Kept as fallback.** |
> | **C** | **KYA — identity & control for agent spend** ✅ | **Sells in 90 days. No licence. Protocol tailwind.** |

**Kicker:** **The only one where being early is itself the moat.**

### Visual
Three-row table. Rows A and B dimmed/greyed; row C at full contrast with a check.

### Speaker notes
"We looked seriously at two others. Early-warning default risk for lenders — real pain, but it
needs continuous account access from both sides, competes with every bank's in-house risk team,
and we can't prove the model without lending data we don't have.

And helping insurance beneficiaries recover rejected claims — genuinely underserved, but it's a
services business before it's a product. We've kept it as a fallback.

We chose this one because it's the only one where we can sell in ninety days *and* be positioned
for the protocol."

**This is your rigour slide.** If you're short on time, cut slide 11 — never this one.

---

# SLIDE 11 — NEXT 90 DAYS
**Runtime: 45 sec**

### On-slide
> ## Next 90 days
>
> | Weeks | Milestone |
> |---|---|
> | 1–3 | **Prototype:** agent blocked outside its mandate, replayable in the audit view |
> | 2–6 | **Partner bank / PA** — confirm the no-licence path in writing |
> | 4–8 | **Paper:** *What UAP must get right about agent fraud and dispute evidence* |
> | 6–12 | **10 discovery calls → 2 paid design partners.** Goal is pricing discovery, not revenue |

**Kicker:** **Success at 90 days is not ARR.**

### Visual
Simple 4-row Gantt. One bar per row.

### Speaker notes
"Ninety days: a working prototype that blocks a rogue agent live, the no-licence path confirmed
in writing, the paper circulating among the people writing the rules, and two paying design
partners — where the goal is discovering what they'll pay per agent, not the revenue itself."

---

# SLIDE 12 — THE ASK
**Runtime: 45 sec**

### On-slide
> ## What we need from you
>
> **1. Two kinds of intro**
> Companies running agents that touch spend · payments risk at a bank or PSP · the iSPIRT orbit
>
> **2. A hard review of our threat model** — before we publish
>
> **3. One judgment call**
> Is our first customer the company *running* the agents, or the platform *selling* them?

### Visual
Three large numbered blocks. Then the closing line as the final full-bleed statement:

> # Your bank knows you.
> # Nobody knows your agents.
> ### The ID card, the rulebook, and the security camera for AI that spends money.

### Speaker notes
End on the question, not on a summary. Asking for a judgment call turns a presentation into a
conversation — and it's the fastest way to make a mentor feel useful on the last day.

---
---

# APPENDIX A — THE NUMBERS
*Don't present. Pull up only if asked.*

### On-slide
> ## Unit economics — derived, not picked
>
> | | Value | Derived from |
> |---|---|---|
> | ACV (8-agent customer) | **₹3.0L** | ₹25,000/mo floor × 12 |
> | Cost as % of spend | **50 bps** | ₹3L ÷ ₹6Cr annual spend |
> | Phase 1 (mo 9) | **₹32L ARR** | 8 customers × ₹4L |
> | Phase 2 (mo 18) | **₹2.4Cr ARR** | 26 × ₹6L + platform ₹60L + pilot ₹25L |
> | Phase 3 (mo 30) | **₹7.7Cr ARR** | 60 × ₹7L + platforms ₹2Cr + licences ₹1.5Cr |
> | CAC | **₹75,000** | 40 founder-hours @ ₹1,500 + ₹15K costs |
> | CAC payback | **2.7 months** | ₹75K ÷ (₹3.4L GP ÷ 12) |
> | NRR | **120%** | 8→12 agents, dampened by tier floors, −12% churn |
> | India SAM | **₹560Cr (~$65M)** | 10,000 companies × ₹5L + 60 banks/PSPs × ₹1Cr |

### Two caveats to volunteer before you're asked
- **LTV/CAC of 14× is flattered** by costing founder time at ₹1,500/hr. With a sales team, CAC
  rises 3–5× and it lands at **3–4×** — that's the number we plan against.
- **₹560Cr India SAM is a beachhead, not a prize.** The real prize is being the mandate layer
  when consumer volume arrives, and the fact that the product is protocol-shaped and exports.

### Speaker note
Say **"these are hypotheses we've derived, not validated"** once, early. Then you can be as
specific as you like without being exposed.

---

# APPENDIX B — THE HARD QUESTION
*Rehearse until automatic. This is the one that can unravel the pitch.*

> ### "The transaction already records what it was paid for — can't you just tell which agent did it?"

**Step 1 — concede, immediately and specifically.**
"Often yes. If you run one grocery agent and one ad agent, the merchant name tells you. And your
own app logs already record which agent called which API."

**Step 2 — pivot. The ID is for the decision, not the record.**
1. **The rail decides before it knows the reason.** The reason arrives *with* the request, from
   the requester. You can't use the spender's own claim to decide whether to permit the spend.
2. **Knowing who did it doesn't let you stop them.** One shared credential = one lever: kill it
   and break all five agents. Knowledge isn't control.
3. **One credential is one limit.** The ads agent can eat the procurement budget.
4. **The memo is written by the party under suspicion.** A prompt-injected agent writes whatever
   looks legitimate. Self-reported intent isn't evidence.
5. **The bank and merchant can't see your logs** — and a third-party agent gives you none.

**Step 3 — the analogy.** Five employees sharing one office keycard. The log says the server
room opened at 2 a.m. and you can guess who. You still can't revoke just that person, still
can't give one of them server-room access and not another, and **the door has to decide whether
to open before anyone explains why they're there.**

### Other questions worth having ready
- **"Do you need a licence?"** → No. Credentials are issued by a partner bank or PA; we never
  hold or move funds. Confirming it in writing is a 90-day milestone.
- **"Per-agent virtual cards already exist."** → Yes, and the card is our enforcement mechanism,
  not our moat. Commodity rails are deliberate — it's why we need no licence.
- **"Isn't this just fraud detection?"** → Fraud detection asks *does this look like this
  human?* We ask *did this agent stay inside its granted authority, and can we prove it?*
- **"Why won't NPCI/the banks build it?"** → NPCI has said they won't deploy inside banks'
  environments. Banks will each build it once, for themselves, in 18 months — and a neutral
  audit trail is more credible in a dispute than one written by a party to it.
- **"What have you built?"** → *"Nothing shipped — that's the next three weeks."* A clean "not
  yet" with a specific plan beats a vague "we're working on it."

---
---

# NOTES FOR WHOEVER BUILDS THE TEMPLATE

These are structural, not stylistic — they'll hold in any template you use.

1. **One idea per slide.** Every slide above has a single kicker line. If a slide has two
   takeaways, it's two slides.
2. **Numbers get their own size tier.** `25–50 bps`, `₹7.7Cr`, `2.7 months` should be the
   largest text on their slides — bigger than the headings.
3. **The kicker lines are the deck.** If someone photographs only the kickers, they should still
   understand the pitch. Give them a distinct visual treatment.
4. **Slides 6 and 7 need breathing room** — they're the persuasive core. Fewer elements, more
   space, slower delivery.
5. **Use struck-through/dimmed treatment deliberately** on slides 6 and 10. Showing what you
   *rejected* is the argument; it has to read as rejected at a glance.
6. **Don't put the speaker notes on the slides.** The detail in this file is for your mouth, not
   the screen. Every paragraph you paste onto a slide is a paragraph the room reads instead of
   listening to you.
7. **Appendices stay hidden** until asked. Having them and not needing them is the flex.
