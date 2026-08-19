# "But we already name our agents and give them permissions"
## The hardest objection to KYA — and the answer

Companion note — 29 July 2026

---

## The objection

> *"When we build an agent, we already name it and give it specific permissions and
> capabilities. `ProcurementBot` can call `pay_vendor`, max ₹50,000, these vendors only. That's
> agent identity and that's a mandate. It's a config file. Why does anyone need a company for
> this?"*

**This is the sharpest attack on the idea. Concede the true part immediately — then show where
it breaks.**

---

## The one-line answer

> **What you build today is *self-asserted, in-process capability*.
> What's missing is *third-party-verified, out-of-process authority*.**

Or in a form every engineer understands instantly:

> **Agent permissions today are client-side validation. For money.**

Nobody ships a payment system where the client enforces the rules and the server just trusts
it. But that is precisely the current state of agent spending: the constraint lives inside the
agent, and the bank — the actual server — has no idea what the agent was supposed to be allowed
to do, so it approves everything.

---

## The analogy that lands best: this is the OAuth moment

An app declaring in its own source code *"I only need read access"* is meaningless. That's why
OAuth exists: the **resource owner** issues a scoped token, and the **resource server**
enforces it. The app's own opinion about its scope was never the security boundary.

Agent frameworks today are at the *"the app declares its own scope"* stage.

**KYA is the OAuth moment for agent spending.**

---

## Where the config-file version breaks — five failures

### 1. Enforcement is inside the thing being constrained
This is the fatal one.

If the spending limit is a check in the agent's own code, then the agent — **and anything that
compromises the agent** — is inside the trust boundary. A prompt injection that redirects
behavior is on the *same side of the fence* as the limit. The limit becomes advisory.

The security principle: **a control must be enforced by something the controlled party cannot
modify.**

Move enforcement to the credential — a virtual card that *declines* over ₹5,000 no matter what
the agent believes — and compromising the agent no longer moves the limit. The blast radius
stops at the rail.

> In-process permission is a *preference*. Out-of-process authorization is a *control*.

### 2. The name has no standing outside your process
`ProcurementBot` is a string in your repo. It means nothing to the bank, the merchant, the card
network, or the auditor. When that transaction hits the rails, **there is no field carrying
"ProcurementBot"** — the bank sees a card number and nothing else.

Identity that the counterparty cannot verify isn't identity. It's a variable name.

And note what KYC exists to replace: **self-declared identity.** Nobody accepts "I say I'm
this person." The entire point is third-party attestation. Agent permissions today are back at
self-declaration.

### 3. Capability is not authority
- *"This agent has the `pay_vendor` tool"* → **capability**. What it can technically do.
- *"This agent may spend ₹5,000/week at these merchants, on behalf of Principal X, derived from
  X's actual capacity, until 31 August, revocable instantly"* → **authority**.

Your config expresses the first. It **cannot** express the second, because authority requires a
relationship to the principal's real financial capacity — and your code doesn't know the user's
balance, credit limit, or exposure across their other agents. Only the bank does.

*This is why "an agent can never be mandated beyond its principal's capacity" cannot be
implemented in the agent. The agent doesn't have the information.*

### 4. It doesn't survive a trust boundary
When *you* build the agent, you can trust your own config. But the point of an agent **economy**
is that agents you didn't build will transact with you and on your behalf:

- third-party agents on someone else's platform
- an agent your vendor runs
- an agent embedded in software you bought
- an agent whose model was silently updated last night

**There is no shared config file across companies.** Cross-organizational trust requires an
identity a third party issues and both sides can verify. That's a protocol problem, not a code
problem — and it's why NPCI, Visa and Google are all writing one rather than telling developers
to be careful.

**Even inside one company:** that permission lives in a repo, changeable by any engineer with
commit access, with zero separation of duties from finance. The person operating the agent
should not be the person who can raise its spending limit. That fails basic control design, and
an auditor will say so.

### 5. Config is not evidence
A dispute requires proving **what the mandate was at the moment of the transaction** — not what
your config says today. A repo can be edited afterward. "Our code had a limit" is not evidence
in a chargeback; a signed, timestamped, tamper-evident mandate is.

Evidence needs to be attested by a party with no interest in the outcome. That's structurally
not you.

---

## Two more, briefly

**Revocation speed.** Rogue agent → you fix config and redeploy: minutes to hours. Credential
revocation happens at the rail, instantly, whether or not the agent cooperates. And you cannot
redeploy an agent you don't control.

**Fragmentation.** Every framework expresses permissions differently. A bank cannot underwrite
risk across fifty bespoke permission schemes. **The standardization *is* the product** — that's
what a protocol is for.

---

## The employee analogy (best for a non-technical mentor)

A company gives an employee a job description: *"you may approve spending up to ₹50,000."*
That's the config.

But the **enforcement** is a corporate card with a limit the bank sets. And the **evidence** in
any dispute is the bank statement, not the job description.

Nobody says *"we don't need card limits, we have job descriptions."* Both exist, because one is
**intent** and the other is **enforcement** — and only one of them survives contact with a
motivated adversary or an auditor.

**Your agent's config is the job description. We're the corporate card.**

---

## Concede this honestly — it sharpens the product

In-process permissions **are** sufficient when all five of these hold:

1. You built the agent, and
2. you control the runtime, and
3. no counterparty needs to verify anything, and
4. nobody will dispute the transaction, and
5. no auditor needs independent evidence.

**Break any one and you need an external layer. Money breaks all five.**

### The product insight hiding in this objection
This tells you your **design-partner profile**. If a company's own config genuinely covers it,
that company is not a customer yet.

Your customer is where one of the five conditions breaks:

- **many** agents (attribution and revocation get hard)
- **third-party** agents (no shared config exists)
- **real money** (losses are uncapped)
- **an auditor** asking who authorized a payment
- **a bank** asking what controls exist before extending limits

Use this to qualify discovery calls. It's a sharper filter than "do you use AI."

---

## Say-it-out-loud version (~40 seconds)

> "You're right that you can name an agent and scope its tools — and if you build the agent, run
> it yourself, and nobody ever disputes the payment, that's genuinely enough.
>
> But three things break. First, the limit is enforced *inside* the agent — so a prompt
> injection is on the same side of the fence as the limit. A control has to be enforced by
> something the controlled thing can't modify. Second, the name doesn't leave your process:
> when that payment hits the rails, there's no field carrying 'ProcurementBot' — the bank sees a
> card number, so it can't apply your rules or produce evidence for a dispute. Third, your code
> can't know the user's actual capacity, so it can't derive a cap from it. Only the bank can.
>
> It's the same reason OAuth exists. An app declaring in its own source that it only needs read
> access is meaningless — the resource owner issues a scoped token and the resource server
> enforces it. Agent frameworks today are at the 'app declares its own scope' stage. We're the
> OAuth layer for agent spending.
>
> Put simply: what exists today is client-side validation, for money."

---

## Where this belongs in the deck

Don't add a slide — you're already at ten. Put this in **Q&A prep**, because it's the question a
sharp mentor asks, and answering it cleanly is worth more than a slide would be.

**But do steal one line for the architecture slide:**
> *"The mandate is enforced at the credential, not inside the agent — so compromising the agent
> doesn't move the limit."*

That single sentence pre-empts the objection and shows the architecture was designed with an
adversary in mind.
