# Why Agent Identity?
## And what it means that KYA has no mandate yet

Companion note to the KYA pitch — 29 July 2026

---

# PART 1 — The "no mandate" problem

## The objection, stated fairly

**KYC is a compelled purchase.** Banks don't run KYC because it's good business. They run it
because PMLA and the RBI KYC Master Direction require it, and non-compliance costs penalties
and license risk. Compliance budgets are the most reliable budgets in financial services —
nobody has to be persuaded.

**KYA has none of that.** No regulation requires it. No protocol specifies it yet. Which means
nobody is *forced* to buy, and "you should want this" is a much weaker sale than "you must
have this."

**This objection is correct.** Do not argue with it. Reframe it.

---

## The reframe: three forces that compel purchase before a mandate exists

### 1. Loss, not law
The question *"who pays when the agent buys the wrong thing?"* already has an answer today,
and the answer is: **the company whose agent did it.** That's an uncapped, unhedged,
unmonitored loss sitting on the books right now.

Loss prevention is a faster sale than compliance. Ramp and Brex didn't sell against a
mandate — they sold against uncontrolled spend, and built enormous companies doing it. Nobody
regulates corporate cards into existence. Leakage does.

### 2. The mandate already exists — it just can't be satisfied for agents
**This is the strongest version of the answer, and it's non-obvious.**

An agent paying a vendor from a corporate account does **not** escape existing rules:

- **Internal financial controls** reporting under the Companies Act requires that payments have
  demonstrable authorization. The statutory auditor asks: *what was the authority for this
  payment, and who approved it?*
- **The bank's own AML/KYC obligations** still attach to that account and its transactions.
- **DPDP** still governs the data the agent touches.

So when an agent moves money and the auditor asks who authorized it, **there is currently no
answer.** The mandate isn't missing — the *evidence* is.

> **KYA doesn't create a new compliance requirement. It makes an existing one satisfiable for
> a new kind of transactor.**

That sentence is your best sales line and your best answer to this objection.

### 3. Pre-mandate is the only time you can become the reference implementation
KYC's mandate created an entire industry — Onfido, Persona, Signzy, HyperVerge, IDfy — *after*
the rule landed. The winners were the companies already built when it did.

UAP plus RBI will produce agent rules. Being early to an unwritten mandate is not a weakness in
the plan; **it is the plan.** The window is open precisely because the rule isn't written.

---

## The one-sentence resolution

> **"KYC is a compliance purchase. KYA today is a loss-prevention purchase that becomes a
> compliance purchase. We'd rather sell on pain now and inherit the mandate later than wait for
> the mandate and arrive with everyone else."**

**And the honest risk, stated out loud:** pre-mandate means we must sell on demonstrated pain,
not fear of the regulator. That's exactly why the wedge is B2B — real losses, real audit gaps,
real budget — and not consumer, where nothing hurts yet.

*Saying the risk before the mentor does is worth more than any slide.*

---
---

# PART 2 — Why does agent identity need to exist at all?

## The skeptic's version of the question

> *"The agent acts on my behalf, using my credentials. My identity is already verified. Why
> does the agent need one of its own?"*

Six reasons. The first two are structural — without them the product is impossible, not just
weaker.

---

### 1. Identity is the unit of revocation
Five agents sharing your credential. One misbehaves.

- The log says **you** did it — attribution has collapsed.
- You cannot revoke one without revoking all. Your only kill switch is nuclear: freeze the
  card, break all five.
- You cannot rate-limit one, scope one, expire one, or tell which one is compromised.

This is the same reason SSH keys are per-machine, API keys are per-service, and SIMs are
per-device. **You can only revoke what you can name.**

### 2. Bounded authority requires something to bind it to
Your bank account can pay anyone, any amount. An agent buying groceries should be able to pay
three merchants, up to ₹5,000 a week, until next month.

That narrower authority has to *attach* to something. **Delegation requires a delegate.**

No agent identity → nothing to attach a mandate to → the agent silently inherits the
principal's full capacity. Which is exactly the failure mode we're trying to prevent, and it's
why "an agent can never be mandated beyond its principal's capacity" is a structural
requirement rather than a nice policy.

### 3. Disputes are arguments about who authorized what
Card liability today rests entirely on a distinction: **was the human present or not?**
Card-present vs card-not-present, CVV, 3DS — the whole framework allocates loss based on who
was there and what they proved.

An agent transaction is a **third category the liability framework doesn't have.** To
adjudicate it, the record must name the agent, its mandate *at the time of the transaction*,
and its principal.

**Anonymous automation is unadjudicable.** Which means the bank eats the loss, or the merchant
does — and both will respond the same way: block agents.

### 4. Merchants need it as much as users do — the half everyone forgets
Today a merchant has exactly one tool against automated traffic: **block it.** Bots mean
scalping, card testing, scraping, credential stuffing. Bots are the enemy.

If a legitimate buying agent is indistinguishable from a hostile bot, **merchants will block
your good agents.** So agentic commerce doesn't only have a fraud problem — it has a
*false-negative* problem, and that one blocks revenue on both sides.

Agent identity is what lets a merchant say: *this is a verified agent of a verified customer,
let it through, and here's who to bill.*

**This is why Visa's protocol is literally called Trusted Agent, and why signed agent identity
is being pushed at the infrastructure layer.** Demand for this is bilateral — buyer side *and*
merchant side. That doubles the eventual market and it's a strong slide-4 talking point.

### 5. Behavioral monitoring needs a subject
*"Is this agent acting like itself?"* requires an **itself**.

Anomaly detection is per-entity by construction. Pool agent traffic under the human's
identity and two things break at once: the human's baseline is destroyed (that's the 3 a.m.,
forty-calls-a-second problem), and no per-agent baseline can ever be built.

**Identity is a precondition for the behavioral layer, not a companion to it.**

### 6. An agent is the first financial actor whose instructions a stranger can rewrite
This is the one to say out loud if you only get one.

Your agent runs on someone else's model, on someone else's orchestration platform, updated
without your knowledge, and it reads untrusted content from the open internet. **Prompt
injection means the instruction source may not be the principal.**

A human employee with a corporate card does not get reprogrammed by reading a web page.

So you need to bind *"what was this agent authorized to do"* **separately and cryptographically**
from *"what did someone tell it to do"* — because the second one is attackable and the first
one must not be. That separation is impossible without an identity to hold the authorization.

---

## The pattern argument (use this if the mentor is technical)

Every time computing added a new class of actor, that class got its own identity layer. Without
exception:

| New actor | Identity layer it forced |
|---|---|
| Humans | usernames, passwords |
| Machines | service accounts, mTLS certificates |
| Workloads | SPIFFE / workload identity |
| Devices | SIM, IMEI |
| Applications | API keys, OAuth clients |
| **Agents** | **← this is happening now** |

Agents are a new class of actor that holds spending authority. **This is the most repeated
pattern in the history of computing infrastructure.** It isn't a speculative bet on whether
agent identity happens — only on who builds it.

---

## Say-it-out-loud versions

**15 seconds:**
> "Because you can't revoke, limit, or blame something you can't name. Five agents on one
> credential means one identity, one kill switch, and no way to know which one went wrong."

**45 seconds:**
> "Three reasons. First, identity is the unit of revocation and of authority — an agent needs
> narrower power than its owner, and there's nothing to attach narrower power to unless the
> agent is a nameable actor. Second, disputes are arguments about who authorized what; card
> liability today turns entirely on whether the human was present, and an agent is a third
> category that framework doesn't have — so anonymous agent traffic is unadjudicable, and
> unadjudicable means blocked. Third, and this is the one people miss: merchants need it too.
> Their only tool against bots today is to block them. If a good agent looks like a bad bot,
> good agents get blocked. That's why Visa's protocol is called *Trusted Agent* — the demand
> is bilateral.
>
> And the reason it can't just borrow the human's identity: an agent is the first financial
> actor whose instructions a stranger can rewrite mid-transaction. Prompt injection means the
> instruction source may not be the principal. So authorization has to be bound
> cryptographically to the agent, separately from whatever it was told to do."

---

## Where this lands in the deck

- **Part 1** becomes your answer to *"who is compelled to buy this?"* — and the line
  *"we don't create a new compliance requirement, we make an existing one satisfiable for a new
  transactor"* is strong enough to move onto the business-model slide.
- **Reason 4 (merchant side)** is new material for the deck — it doubles the market story and
  is not in the current slides. Worth adding one line to the architecture slide.
- **Reason 6 (prompt injection)** is your best single sentence in the whole pitch. It's the
  reason this problem is genuinely new rather than a rebrand of fraud detection.

**One thing to verify before citing it:** RBI has been actively examining AI governance in
financial services. If there's a live committee or published framework, it strengthens Part 1
considerably — check the current status rather than describing it from memory, and if unsure,
leave it out. The argument stands without it.
