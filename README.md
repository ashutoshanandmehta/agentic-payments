# Delegated payments for AI agents

MS research. IIT Kanpur. Supervisor: Prof. Vimal Kumar.

**The question:** when an AI agent pays for something, is it allowed to, and can you
prove it afterwards?

## Scope

The work starts at the moment the agent tries to pay. The cart is already full, and
something else chose the products and picked the shop.

Product search, price comparison and shop selection are agentic commerce. Out of scope.

## What runs here

A simulator with real UPI-shaped rails: a double-entry ledger, a two-leg payment with
a suspense account in between, injectable failures, and a reconciliation sweep. On top
of it sits the piece this thesis is about — an **order gate** that checks whether a
payment matches what the user actually agreed to buy.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

.venv/bin/python src/cli.py consent      # the finding, in one command
python3 src/cli.py --fresh demo          # the full payment lifecycle, narrated
python3 tests/test_sim.py                # 44 tests: rails, ledger, recon
.venv/bin/python tests/test_consent.py   # 16 tests: the order gate
.venv/bin/python tests/test_vcard.py     # 8 tests: what the virtual-card hop costs
```

## Two ways to move the money

**Direct.** One payment, user's bank straight to the merchant, governed by the user's
mandate. This is `src/orchestrator.py`.

**Via an agent virtual card.** Two payments with a stop in between — the user's money
loads onto a card the agent controls, then the card pays the merchant. This is
`src/vcard.py`. It is what an agent-held credential looks like if the credential also
holds funds.

The second model is implemented so its costs can be measured rather than argued about.
`tests/test_vcard.py` asserts three of them:

1. **Merchant scoping stops working.** On the load, the payee is the card, not the shop,
   so the mandate has to name the card. A mandate that says "Brewhouse only" becomes a
   mandate that says "this card only", and the card can then pay anyone. The test loads
   against a Brewhouse-scoped mandate and pays CloudHost successfully — while the same
   payment made directly is refused.
2. **Float gets stranded.** Load succeeds, spend fails, and ₹499 sits on the card. The
   reconciliation sweep does not find it, because nothing is stuck mid-transaction. Only
   a deliberate `vcard.sweep()` returns it.
3. **The audit chain is severed.** The load and the spend are separate transactions. The
   load record names the card, never the merchant. The link between them exists only
   because the application kept it.

Also: mandate headroom is consumed by the *load*, so loading ₹600 for a ₹499 purchase
burns ₹600 of the user's cap whether or not the purchase happens.

In production this arrangement holds customer funds, which in India needs a PPI or PA
licence. That is a funding question, not a simulation question.

## The gap this closes

A mandate says how much the user may spend and with whom. A policy says what the
operator permits. **Neither knows what the user agreed to buy.**

So a ₹5,000 mandate for `brewhouse@ybl` happily authorises a ₹600 payment to
`brewhouse@ybl`, even when the basket the human saw came to ₹118. Every limit is
respected and the user is still overcharged.

`src/cli.py consent` shows exactly this:

```
User agreed to ₹118.00.  Agent is asking for ₹600.00.

  WITHOUT the order gate (UPI today)
    ALLOWED   15 checks

  WITH the order gate
    REFUSED   21 checks
      x amount_matches_order   paying ₹600.00 against agreed ₹118.00
```

The gate is **off by default**, so the base system behaves the way UPI does today and
the comparison is one flag.

## The finding: who signs the order matters less than expected

The obvious next question was who should sign the order — the agent, the merchant, or
both. `tests/test_consent.py` runs all three against a *self-consistent* inflated
order, one whose lines really do add to ₹600.

All three approve it.

A signature proves who wrote a record. It does not prove the record is true. Once the
order is the only surviving evidence of the agreement, there is nothing left to compare
it against.

What refuses it is a per-transaction ceiling close to the real basket size. **The
protection comes from the limit the user set, not from who signed the order.**

Requiring both signatures also has a cost that shows up as a test: if merchants must
sign and no merchant has integrated, every payment stops, including the honest ones.

## How a payment flows

```
standing instruction + event
        │
        ▼
   ┌─────────┐  intent   ┌──────────────────────────┐  authorised  ┌────────┐
   │  Agent  │ ────────▶ │ order gate → mandate →   │ ───────────▶ │ Switch │
   │         │           │ policy   (deterministic) │              │ (NPCI) │
   └─────────┘           └──────────────────────────┘              └───┬────┘
    proposes                       disposes                            │
                                                             debit ◀───┴───▶ credit
                                                                 │           │
                                                        remitter bank   beneficiary bank
                                                                 └──▶ suspense ──▶
```

The agent cannot move money. It emits a proposal and nothing else — `src/agent.py`
imports no rails, and a test asserts that so it stays true.

The order gate runs **before** the mandate on purpose. "Can they afford it" is a
different question from "did they agree to it", and only the second one notices a ₹600
charge against a ₹118 basket.

## Layout

```
src/consent.py       the order, Ed25519 signing, and the order gate   <- the contribution
src/policy.py        mandate validation + operator policy + the order gate
src/core.py          Money as integer paise, VPA/RRN/UMN, NPCI response codes
src/models.py        domain objects and the transaction state machine
src/store.py         SQLite, double-entry ledger, idempotency, audit trail
src/rails.py         banks, NPCI-style switch, fault injection
src/agent.py         Claude planner + deterministic fallback (imports no rails)
src/orchestrator.py  lifecycle state machine
src/recon.py         reconciliation sweep and ledger audit
src/sim.py           wiring and the demo world
src/cli.py           command line
src/api.py           FastAPI REST layer

tests/test_sim.py      44 tests: money, idempotency, mandate, policy, faults, recon
tests/test_consent.py  16 tests: the order gate and the signing experiment

docs/thesis/         problem statement
docs/research/       fact base, corrections, forward assumptions
sim/                 earlier standalone prototype, superseded by src/
```

## Provenance

The rails, ledger, reconciliation and CLI came from a separate simulator
(`~/Downloads/upi-agent-sim`), merged in on 20 Aug 2026. The order gate, the signing
experiment and `tests/test_consent.py` are this project's addition. Both test suites
pass together: 44 + 16.

## How facts are marked

- `PRIMARY` — checked against the actual source
- `SECONDARY` — someone reliable reported it, not verified directly
- `UNVERIFIED` — believed, not checked. Do not build on it.
- `CONTESTED` — sources disagree, or it was checked and failed

`docs/research/corpus-corrections-2026-08.md` records claims that turned out wrong,
including three load-bearing ones. That file is the standard, not an embarrassment.

## Still to verify

- **P3P prior art — highest priority.** Pine Labs' P3P (11 Jun 2026) runs agentic
  payments on UPI ReservePay with an identity layer called Grantex. Its public docs do
  not describe binding a payment to an agreed order, but the docs stop at the quickstart.
  Read the SDK or email `pgintegration@pinelabs.com`. If P3P already does this, the
  contribution needs rethinking. See `docs/protocols.html`.
- Read **NPCI OC 228** section by section. NPCI's site blocks automated fetching.
- Check whether **Juspay** has published an AP2-to-UPI binding. If they have, part of
  the novelty is gone.
- Find any RBI or NPCI statement on whether agent payments sit inside the e-mandate
  exemption. That decides whether agent payments on UPI are already legal.

## What this is not

Simulated rails, not a PSP integration. No real NPCI connection, no settlement windows,
no bank cut-offs, no UPI PIN cryptography, no scheme compliance. `SIM-` prefixed
response codes are this simulator's own, marked so nobody mistakes them for switch
responses.
