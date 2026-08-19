# Trust Layer for Agentic Payments
### Final presentation — 29 July 2026

---

## Slide 1 — Title

**Guardrail**
*The audit and fraud layer for AI agents that spend money.*

[Your name] · [Program name] · 29 July 2026

---

## Slide 2 — The shift that just happened

Payments were always **human → merchant**.

In the last 12 months that changed:

| Who | What they shipped |
|---|---|
| Google | Agent Payments Protocol (AP2) |
| Visa | Intelligent Commerce / Trusted Agent Protocol |
| Mastercard | Agent Pay |
| OpenAI + Stripe | Agentic Commerce Protocol |
| Amex | agentic commerce pilots |

Every major network independently concluded the same thing:
**software will soon be the buyer, not the human.**

And in India, NPCI has begun work on a **Unified Agentic Protocol (UAP)** —
built on top of **UPI Circle**, the delegated-payments feature that is already live.

---

## Slide 3 — The gap nobody has filled

All of these protocols answer the same question:
> *"How does an agent get permission to pay?"*

**None of them answer the two questions that follow:**

1. **How do you stop a rogue agent?**
   A prompt-injected or malfunctioning agent has valid credentials. Every existing fraud
   model is trained on *human* behaviour — time-of-day, velocity, device, geography.
   An agent breaks all of those assumptions by design. It is 3 a.m. traffic, 40 calls a
   second, no device fingerprint. Today's models either block everything or nothing.

2. **When it goes wrong, who pays?**
   A chargeback needs evidence. For an agent transaction, the evidence is:
   *what was the agent instructed to do, what did it actually do, and where did the two
   diverge?* No protocol currently specifies that record. Without it, no dispute is
   adjudicable — which means banks cannot underwrite the risk, which means they will
   throttle agentic payments regardless of how good the protocol is.

**The protocols define the road. Nobody has built the brakes or the black box.**

---

## Slide 4 — What we build

**Guardrail sits between the agent and the payment rail.**

```
   AI Agent
      │
      ▼
┌───────────────────────┐
│      GUARDRAIL        │
│                       │
│  1. Mandate check     │  Is this purchase inside the authority
│                       │  the human actually granted?
│                       │
│  2. Agent-native      │  Anomaly detection trained on agent
│     anomaly engine    │  behaviour, not human behaviour
│                       │
│  3. Replayable        │  Signed, tamper-evident log: instruction
│     audit trail       │  → reasoning → action → outcome
└───────────────────────┘
      │
      ▼
  UPI Circle / card rail
```

Three primitives. One sentence:
**we make agent spending auditable, so banks can afford to allow it.**

**Who pays us:** banks, PSPs and agent platforms — per-transaction or per-seat.
They cannot launch agentic payments without a defensible dispute record. That is a
compliance line item, not a nice-to-have.

---

## Slide 5 — Why now (the 12-month window)

UAP is **a draft**. NPCI is writing it *"in consultation with industry"* right now.

That phrase is the whole opportunity:

- Once a protocol is finalised, everyone competes on execution from the outside.
- **While** it is being written, a small group is in the room shaping it.

India Stack precedent: the people in the early UPI / Account Aggregator / OCEN
protocol rooms — largely through **iSPIRT** — went on to found or run the companies
that dominated those rails.

**We are not waiting for the spec. We are trying to be useful to the people writing it.**

---

## Slide 6 — Our wedge: don't wait for UAP

UAP is built on **UPI Circle**, which is **live today**. So we can build now.

**The prototype (2 weeks):**
An AI agent transacting under a Circle-style delegation, with Guardrail watching:

- a mandate the human sets ("groceries, ₹5,000/month, these 3 merchants")
- the agent attempting a purchase **outside** that mandate → blocked, flagged, logged
- a replay view: *here is what the agent was told, here is what it did, here is the divergence*

**The paper (parallel):**
*"What UAP must get right about agent fraud and dispute evidence"* — threat model for
agentic UPI, why human-pattern fraud models fail on agent traffic, and the minimum
contents of an agent audit trail for a chargeback to be adjudicable.

The industry has publicly admitted this is unsolved. Nobody has written the serious answer.

**Circulation:** iSPIRT volunteer onboarding, pi-labs network, IIT-K faculty / C3iHub,
NPCI's own consultation process.

**Output of this phase is not revenue. It is position** — being the team with the working
demo in the room where the rules are written, before the market exists.

---

## Slide 7 — How we got here (we evaluated three)

| | Idea | Why not now |
|---|---|---|
| **A** | **Real-time default risk** — monitor account irregularities, flag likely defaulters before the first missed EMI | Real pain, but: needs continuous account access from both borrower and institution (DPDP + AA consent friction), competes directly with every bank's in-house risk team and existing bureau/AA analytics players, and we cannot prove the model without lending data we don't have. **Long sales cycle, no wedge.** |
| **B** | **Insurance claim recovery** — most beneficiaries stop after the first rejection letter, though many claims are recoverable | Genuinely underserved and emotionally sharp. But it's a services business before it's a product, has existing players in the grievance-redressal space, and revenue depends on regulatory positioning we haven't validated. **Kept as a candidate — not a protocol-timing bet.** |
| **C** | **Agentic payments trust layer** ✅ | **Timing window is open and closes.** Buyers are already publicly asking the question. Demo buildable on live infrastructure. Our advantage compounds with the spec instead of competing with incumbents. |

*We chose C because it is the only one where being early is itself the moat.*

---

## Slide 8 — Next 90 days

| Weeks | Milestone |
|---|---|
| 1–2 | Working prototype on UPI Circle — mandate check, one blocked rogue action, replayable log |
| 3–6 | Technical paper drafted; threat model reviewed by 2–3 payments-security people |
| 6–8 | iSPIRT volunteer onboarding; identify who is convening the UAP consultation |
| 8–12 | 5 structured conversations with bank/PSP risk teams → convert the paper's threat model into a paid pilot spec |

**Success at 90 days is not ARR. It is:** a demo that works, a paper that circulates,
and three named people in the UAP conversation who know who we are.

---

## Slide 9 — What we're asking you for

1. **Intros** — anyone in payments risk / fraud at a bank, PSP, or NPCI; anyone in the iSPIRT orbit.
2. **A hard review of the threat model** before we publish. We would rather be corrected by you than by NPCI.
3. **One honest read:** is "position before product" the right first move here, or should we be
   selling something in 90 days?

---

## Speaker script (~4 minutes)

> "For as long as payments have existed, the buyer has been a human. In the last twelve
> months, Google, Visa, Mastercard, Amex and OpenAI have each shipped a protocol for a
> world where the buyer is software. And NPCI has started drafting India's version, called
> UAP, on top of UPI Circle — which is already live.
>
> Every one of those protocols answers the same question: how does an agent get permission
> to pay. None of them answer the two questions that come next.
>
> First: how do you stop a rogue agent? If an agent is prompt-injected or just malfunctions,
> it holds valid credentials. And every fraud model in production today is trained on human
> behaviour — time of day, velocity, device, location. An agent violates all of those by
> design. It *is* 3 a.m. traffic at forty calls a second. So the models either block
> everything or nothing.
>
> Second: when it goes wrong, who pays? A chargeback needs evidence. For an agent, the
> evidence is what it was told, what it did, and where those diverged. No protocol specifies
> that record. And without it, no dispute can be settled — which means banks can't underwrite
> the risk, which means they'll throttle agentic payments no matter how good the protocol is.
>
> So the protocols are building the road. We want to build the brakes and the black box.
>
> Guardrail sits between the agent and the rail and does three things: checks every action
> against the mandate the human actually granted, runs anomaly detection trained on agent
> behaviour rather than human behaviour, and writes a signed, replayable log of instruction
> to action. Banks and PSPs pay for this because they can't launch without a defensible
> dispute record.
>
> And here's why we think the timing matters. UAP is still a draft — NPCI is writing it in
> consultation with industry right now. Once a protocol is final, everybody competes on
> execution from the outside. While it's being written, a small number of people are in the
> room. That's the India Stack pattern: the people in the early UPI and Account Aggregator
> rooms became the companies that owned those rails.
>
> We're not waiting for UAP. UPI Circle is live, so in two weeks we can demo an agent
> transacting under a delegation, attempting something outside its mandate, getting blocked,
> and being replayable afterwards. Alongside it we're writing the paper the industry has
> admitted nobody has written: what UAP must get right about agent fraud and dispute evidence.
>
> We looked at two other ideas seriously — early-warning default risk for lenders, and
> helping insurance beneficiaries recover rejected claims. Both are real problems. We chose
> this one because it's the only one where being early is itself the moat.
>
> What we'd like from you is intros into payments risk, a hard review of our threat model
> before we publish it, and one honest answer: is position-before-product right here, or
> should we be selling something in ninety days?"

---

## Likely mentor questions — prepared answers

**"Who is your first paying customer?"**
Not a bank. Banks are the eventual buyer but a 9-month cycle. First revenue is an
**agent platform** — anyone shipping a shopping or booking agent in India who needs to tell
their bank partner "we have controls." They have the urgency and can sign in weeks.

**"Why won't Visa/NPCI just build this themselves?"**
They're building the *protocol*, not the monitoring layer — the same way NPCI built UPI but
Razorpay and PhonePe built on top. Protocol bodies define the standard; they don't operate
per-transaction risk products for every participant. Also, a neutral third-party audit trail
is more credible in a dispute than one written by a party to it.

**"Isn't this just fraud detection?"**
Fraud detection asks *"does this look like this human?"* We ask *"did this agent stay inside
its authority, and can we prove what happened?"* The second question is new, and it's the
one that's blocking launches.

**"What have you actually built?"**
Be honest: *"Nothing shipped yet — that's the next two weeks. What we have is the threat
model and the choice of wedge, and we deliberately picked one we can demo on live
infrastructure instead of waiting for a spec."* Mentors respect a clean "not yet" far more
than a vague "we're working on it."

**"What if UAP takes three years?"**
Then UPI Circle delegation and card-network agent protocols still ship, and the problem is
identical. We are not betting on UAP's timeline — we're betting on agents spending money,
which is already happening.

**"Why should the two rejected ideas stay rejected?"**
They shouldn't necessarily — claim recovery is the fallback if agentic payments turn out to
be 3 years early. Say that. Optionality stated out loud reads as maturity, not indecision.

---

## Two things to check before you present

1. **The UAP specifics.** Say *"NPCI has begun work on a unified agentic protocol, publicly
   described as being in consultation with industry"* rather than quoting spec sections or
   dates. If the mentor knows the space and you overstate the detail, the whole pitch loses
   credibility. Confidence about the *problem*, humility about the *spec status*.

2. **Slide 7 is your most important slide.** It's the one that proves you did work rather
   than picked the shiniest idea. If you're short on time, cut Slide 8 — never Slide 7.
