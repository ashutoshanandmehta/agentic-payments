# Delegated payments for AI agents

MS research. IIT Kanpur. Supervisor: Prof. Vimal Kumar.

**The question:** when an AI agent pays for something, is it allowed to, and can you
prove it afterwards?

## Scope

My work starts at the moment the agent tries to pay. The cart is already full, and
something else chose the products and picked the shop.

Product search, price comparison and shop selection are agentic commerce. They are out
of scope.

The payment goes through UPI, India's payment system.

## The gap

UPI makes you name the shop when you create a payment authority. UPI Autopay is locked
to one payee. UPI Reserve Pay blocks money for one specific shop.

But an agent does not know which shop it is paying until the cart is finished.

You can work around it by pre-blocking at every shop the agent might use. Three shops
means Rs 30,000 of the customer's money locked up, and you have to list the shops in
advance. So the honest version of the gap is:

> UPI has no single payment authority that can be spent across an **open** set of
> shops. You can approximate it by naming the shops in advance and paying the capital
> cost, but you cannot express "spend up to Rs 1,000 at whichever grocery shop turns
> out to be cheapest."

## The mechanism

Describing the gap is not a contribution. `arXiv:2604.15367` already published the
observation that instruction origin goes unverified after a mandate is created. Only a
mechanism counts.

The mechanism: four signed records at the payment boundary, and two arithmetic checks
between them.

The records are the authority, the cart, the request, and the settlement. The checks
are: does the request still match the cart, and does the cart fit inside the authority.

Both checks are arithmetic. No language model sits in the approval path, because a bank
cannot refuse a payment on a probability.

## The simulation

`sim/` implements it. 22 scenarios, 16 refused, 6 approved, all matching what they
predicted.

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m sim.run          # all 22 scenarios in the terminal
./.venv/bin/python -m sim.web          # web interface at http://localhost:8000
```

The most interesting result is about a question I had not settled: **who should sign
the cart?**

It matters less than expected. A cart claiming Rs 600, internally consistent, against a
human who only agreed to Rs 118, is approved whether the agent signs it, the shop signs
it, or both do. A signature proves who wrote a record, not that the record is true.

What stops it is a tight limit in the authority. **The protection comes from the limit
the human set, not from who signed the cart.**

## Files

```
docs/thesis/
  problem-statement.md          the problem, scoped to the payment boundary
  thesis-problem-definition.md  earlier version, predates the narrowing

docs/research/
  corpus-corrections-2026-08.md             claims that turned out wrong. read first.
  agentic-payments-fact-base-2026-08.md     verified facts with sources
  assumptions-forward-2026-08.md            what I assume, and what would disprove it
  agentic-commerce-india-research-report.md background, mostly out of scope now

sim/                            the simulation. see sim/README.md
```

## How facts are marked

- `PRIMARY` - checked against the actual source
- `SECONDARY` - someone reliable reported it, not verified directly
- `UNVERIFIED` - believed, not checked. Do not build on it.
- `CONTESTED` - sources disagree, or it was checked and failed

`corpus-corrections-2026-08.md` records claims that were wrong, including three that
were load-bearing. That file is the standard, not an embarrassment.

## Still to verify

- Read **NPCI OC 228** section by section. Two claims depend on it, and NPCI's site
  blocks automated fetching.
- Check whether **Juspay** has published an AP2-to-UPI binding. They are an AP2 launch
  partner, Indian, and work on UPI. If they have, part of the novelty is gone.
- Find any RBI or NPCI statement on whether agent payments fall inside the e-mandate
  exemption. This decides whether agent payments on UPI are already legal.

## Where to start

1. [`docs/thesis/problem-statement.md`](docs/thesis/problem-statement.md)
2. [`sim/README.md`](sim/README.md)
3. [`docs/research/corpus-corrections-2026-08.md`](docs/research/corpus-corrections-2026-08.md)
