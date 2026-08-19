# `sim/` — delegated payments, simulated

A working model of what happens when an AI agent tries to pay.

The cart is already full when this code starts. Nothing here searches for products or
compares prices — that happens before the boundary being studied.

No bank, no real payment system, no company partnership. Every dependency is one you
already control.

## Run it

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m sim.run              # all scenarios
./.venv/bin/python -m sim.run -v           # add the rail's trace
./.venv/bin/python -m sim.run --list       # scenario names
./.venv/bin/python -m sim.run price-drift  # just one
```

**22 scenarios, 16 refused, 6 approved, all matching what they predicted.**

## The idea in one page

Four things get signed:

- **the authority** — what the human allowed, signed in advance
- **the cart** — what is being bought and from whom
- **the request** — the agent asking to pay
- **the settlement** — the rail agreeing to move money

Two checks run between them:

- **Check A**: does the payment request still match the cart? Nothing changed in between.
- **Check B**: does the cart fit inside the authority? The agent stayed in bounds.

Both are arithmetic. No language model is in the approval path, because a bank cannot
refuse a payment on a probability — it needs a reason it can put in a dispute file.

## Files

```
uap/authority.py    money, and what the human signed in advance
uap/cart.py         the cart, and the request to pay for it
uap/mandate.py      Ed25519 signing; who signs the cart is a setting, not a decision
uap/check.py        the two checks
uap/delegation.py   several people funding one agent
uap/ledger.py       blocking and releasing money
rail.py             the only thing that can approve a payment
scenarios.py        22 scenarios, each stating its expected result first
run.py              the harness
```

## What it tests

**Tampering** — something changed between the cart and the money moving. Price drift
(agreed ₹118, debited ₹162), payee swap, double debit from a retry, a cart whose total
doesn't match its lines, an authority edited after signing.

**Authority** — the agent went outside what was allowed. Wrong shop, wrong category,
single payment over the limit, total budget exhausted, used more times than allowed,
expired.

**Delegation** — several people fund one agent. Whose money pays, what happens when one
person revokes, and what happens when the appliance is sold.

**Cart signing** — an experiment on the open question, described below.

## Three findings

**1. Signing the cart does not stop overcharging.**

This is the answer to "who should sign the cart", and the answer is: it doesn't matter
as much as expected.

The simulation runs the same attack three ways. A cart says ₹600, its lines add to
₹600, everything is internally consistent — but the human only ever agreed to a ₹118
basket. All three signing designs approve it:

- agent signs → approved
- shop signs → approved
- both sign → approved

A signature proves *who wrote the record*. It does not prove *the record is true*.
There is nothing to compare ₹600 against, because the cart is the only record of what
was agreed.

What actually stops it is a tight authority. Change the per-payment limit from ₹800 to
₹150 and the same cart is refused. **The protection comes from the limit the human set,
not from who signed the cart.**

**2. Requiring both signatures has a real cost.** If the shop must sign and no shop has
integrated yet, every payment stops. That is the `sign-both-absent` scenario. Any
proposal requiring merchant participation has to explain how it survives before
merchants adopt it.

**3. One unrestricted grant is a hole in everyone else's limits.** In the household,
Dad limits himself to groceries and transport, and the teenager to dairy. Mum's grant
has no category limit. So the household's real policy is Mum's. Category limits are
only as strong as the loosest grant in the set.

## What this does not do yet

- No real payment system. The ledger is a model.
- The agent is a stub, not a language model.
- Records are signed JSON, not W3C Verifiable Credentials. The shape follows AP2; the
  encoding does not, and does not need to in order to test the claim.
- Time is integer ticks, not real timestamps. Enough to model a revocation arriving
  before a payment, not enough to model network latency.

## Assumptions

The world this runs in is written down in
[`../docs/research/assumptions-forward-2026-08.md`](../docs/research/assumptions-forward-2026-08.md).
The problem it addresses is in
[`../docs/thesis/problem-statement.md`](../docs/thesis/problem-statement.md).
