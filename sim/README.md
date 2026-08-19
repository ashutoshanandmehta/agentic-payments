# `sim/` — delegated agent payments, simulated

A working environment for the two claims in the root README: that the delta between
a signed Intent Mandate and a signed Cart Mandate is measurable drift, and that a
budget delegated to an agent across merchants is a primitive UPI does not have.

Nothing here talks to a real rail. That is the point — every dependency is one you
already control, so the work is not blocked on NPCI, a bank, or a partnership.

## Run it

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m sim.run              # all scenarios
./.venv/bin/python -m sim.run -v           # + agent trace, merchant log, rail trace
./.venv/bin/python -m sim.run --list       # scenario keys
./.venv/bin/python -m sim.run injection -v # one scenario
```

Current state: **15 scenarios, 11 denied, 4 authorised, all matching their predicted
outcome.**

## How it is arranged

```
uap/          the trust layer
├── intent.py       the constraint language  <- the piece AP2 leaves undefined
├── mandate.py      Ed25519 signing; Intent / Cart / Payment mandates; evidence
├── delegation.py   principals, devices, agents, the multi-principal household
├── drift.py        deterministic Intent-vs-Cart evaluation
└── ledger.py       cross-merchant reserve / capture / release

market/       the hostile world
├── catalog.py      products, SKUs, packs
└── merchant.py     MCP-shaped servers with seven adversarial behaviours

agent/
└── shopper.py      a deliberately naive agent

rail.py       the only component that authorises
scenarios.py  15 scenarios, each declaring its expected outcome first
run.py        harness
```

## The four design decisions that carry the weight

**Everything is exact integers.** Money in paise, mass in grams, volume in
millilitres. No float touches a comparison. A payments system that rounds is a
payments system that can be gamed by rounding.

**Unit normalisation is a security control.** A 500g pack advertised at its pack
price against a `≤ Rs 56/kg` ceiling normalises to Rs 58/kg and is refused. Without
normalisation that attack is invisible. Resolution matters too — at paise-per-gram
every offer in the catalogue ties at 6, so prices are held per display unit (kg/l).

**Drift is evaluated before funding is resolved.** A cart that violates its intent
is refused even when the money is there. "Can they afford it" is not "were they
allowed to buy it" — and a system that only asks the first is a spend cap, which
authorises a prompt-injected 10kg order for Rs 540 against a Rs 5,000 limit without
blinking.

**The evaluator fails closed.** Unverifiable signature, unparseable payload,
mismatched reference — all deny. An evaluator that authorises when confused is worse
than none, because it launders the failure as an approval.

## Scenarios

### Adversarial — can the mandate chain catch a hostile merchant?

| Key | Attack | Outcome |
|---|---|---|
| `honest` | none | authorised, cheapest offer, drift 0.00 |
| `unit-confusion` | 500g pack priced as per-kg | denied — `unit_price` |
| `quote-drift` | quoted 15% under the charge | denied — `quote_drift` + 3 more |
| `false-stock` | cheapest SKU hidden | denied — `quantity`, `total` |
| `injection` | instructions in product text, naive agent | denied — `quantity`, `total`, drift 13.40 |
| `injection-defended` | same payload, hardened agent | authorised |
| `substitution` | maida shipped against an atta order | denied — `substitution` |
| `arithmetic` | line total inflated, unit price left innocent | denied — `arithmetic` + 2 more |
| `oversupply` | 2kg delivered against 1kg | denied — `quantity` |
| `rogue-agent` | agent shops off the allow-list | denied — `merchant` |
| `tampered-intent` | signed intent edited after the fact | denied — `signature` |

### Delegation — the shape UPI Circle cannot express

| Key | Situation | Outcome |
|---|---|---|
| `multi-principal` | 3 principals fund 1 shared agent | authorised, funded by Teen |
| `uncovered-category` | nobody's grant covers alcohol | denied at funding |
| `revocation` | Mum revokes; Dad's grant untouched | authorised, funded by Dad |
| `device-reset` | fridge resold and reset | denied, all delegations dead |

## Findings so far

Three things the code surfaced that the documents had not:

1. **Funding resolution in a multi-principal household has no good default.**
   Narrowest-scope-first drains the teenager's Rs 500 dairy grant to buy the
   household's milk before touching either parent's Rs 4,000. Unrestricted-first
   makes the least careful member fund everything. A rail that ships this has to
   pick one and defend it.

2. **One unrestricted grant is a hole in everyone else's scoping.** Category
   scoping is only as strong as the loosest grant in the household. See
   `uncovered-category`.

3. **Unit-price resolution is a security property, not a formatting choice.** Too
   coarse and every offer ties, so a manipulated price is indistinguishable from a
   real one.

Two scenarios initially authorised when they should have denied — `false-stock`
hid the cheapest SKU by *pack* price while the agent shops on *unit* price, so the
attack achieved nothing; and the funding policy's docstring promised
narrowest-scope-first while the code sorted by headroom. Both were real defects in
the model, fixed rather than papered over by adjusting the expectation.

## What this does not do

- No real rail, bank, or NPCI connection, and no live merchant.
- The agent is a deterministic stub, not an LLM. Swapping one in is the obvious
  next step and would make the injection scenarios considerably more interesting.
- Mandates are signed JSON, not W3C Verifiable Credentials. The structure is AP2's;
  the encoding is not, and does not need to be to test the claim.
- No time dimension yet: no mandate expiry, no revocation-latency race against an
  in-flight order. That gap is worth closing next — revocation latency is the
  question a bank will ask first.

## Assumptions

The world this runs in is A7–A15 in
[`../docs/research/assumptions-forward-2026-08.md`](../docs/research/assumptions-forward-2026-08.md).
A7–A13 remove obstacles; **A11 and A15 create them**, and they are the reason this
is a simulation rather than a demo.
