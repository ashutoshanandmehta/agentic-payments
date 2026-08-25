# Trusted delegated payments for AI agents

MS research. IIT Kanpur. Supervisor: Prof. Vimal Kumar.

**The question.** When an AI agent pays for something, is it allowed to, and can you prove it afterwards?

The work starts when the agent tries to pay. The cart is already full. Something else chose the products and picked the shop. Product search and price comparison happen before that boundary and are out of scope.

## What this is

A control layer that sits above UPI and card rails, with a simulator underneath it so every claim can be run.

The agent proposes a payment. A deterministic gate decides. The rail settles. The agent never moves money itself.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

.venv/bin/python src/bench.py            # the test bench at localhost:8010
.venv/bin/python src/cli.py enforce      # who on a UPI payment could run the check
.venv/bin/python src/cli.py rails        # which rail can carry the authority
.venv/bin/python src/cli.py consent      # the order gate, off then on
.venv/bin/python src/cli.py --fresh demo # the full payment lifecycle, narrated
```

## The six components

The first three answer whether the agent may pay. The last three answer whether you can prove what happened.

1. **Agent registration.** A cryptographic identity tying each agent to a verified owner and a host device. Several agents can share one device. Switching off the first leaves the others running.
2. **Authority creation.** The owner sets a per payment ceiling, a period budget, a category scope and an expiry. The authority then binds to a rail.
3. **The order check.** Before settlement, arithmetic confirms the payment matches the order the owner approved and sits inside the authority.
4. **The cross rail receipt.** One signed record binding the registration, the authority, the order and every leg of money that moved. A spend has to chain back to the load that funded it.
5. **Owner control.** A place to see what the agent bought and to switch it off across both rails.
6. **Reconciliation.** Every payment ends in one of three states. Succeeded, failed, or unknown. The unknown state is the one that matters, because payment networks lose certainty about outcomes.

The order check runs before the authority check. Whether the owner can afford a payment is a different question from whether they agreed to it. Only the second one notices a Rs 600 charge against a Rs 118 basket.

Both checks are arithmetic. No language model sits in the approval path, so every refusal produces a reason that can go in a dispute file.

## Two rails, two shapes

The rails work differently and the system models each on its own terms.

**Cards.** The agent gets a scoped token. It holds no value. It is a reference that resolves inside the network to the owner's real card. The network validates the scope at every authorisation, so merchant, category, cap and expiry are all checked before money moves. The money then moves once, owner to merchant.

**UPI.** There is no token. The authority is a block on the owner's own account and the block names one merchant. An agent that does not know its merchant in advance has to be handed money it controls. That means a load leg onto an agent held card, then a spend leg to the shop.

What the second shape costs is measured in `tests/test_vcard.py`. Merchant scope moves to the card. Headroom is consumed by the load. Float can sit on the card when a spend fails.

## Two purchase shapes

Not every purchase has a basket.

**A basket.** The owner agrees a total. Settlement has to match it.

**A meter.** A charging session, a battery swap, a tanker of water. Nobody knows the total until it is over. The owner agrees a rate and a ceiling instead, and settlement is checked against the meter reading. Rs 15.00 per kWh with a Rs 250.00 ceiling settles 11.2 kWh at Rs 168.00 and refuses a padded rate.

## The evidence half

Every payment produces one signed receipt. It binds the registration, the authority, the order and each movement of money, across whichever rails it took.

Verification runs on public keys alone. A third party holding no private key can check that the receipt is intact, that the agent was registered to that owner and still active, that the order carries the signatures it claims, and that the money adds up.

That last check is the one the ledger cannot do on its own. Money left stranded on an agent card is invisible to a reconciliation sweep, because nothing is stuck mid transaction and the books really do balance. The receipt names it.

## Tests

221 tests across eight suites. Every one runs offline.

```bash
.venv/bin/python tests/test_sim.py            #  44  money, idempotency, mandates, policy, faults, recon
.venv/bin/python tests/test_registration.py   #  41  agent identity, credentials, revocation isolation
.venv/bin/python tests/test_authority.py      #  30  rail binding, enforcement, scope, budgets
.venv/bin/python tests/test_metered.py        #  26  rate arithmetic, meter reconciliation, ceilings
.venv/bin/python tests/test_receipt.py        #  25  the chain, stranded float, outside verification
.venv/bin/python tests/test_token.py          #  24  card token scope, single movement, rail comparison
.venv/bin/python tests/test_consent.py        #  16  the order gate and the signing experiment
.venv/bin/python tests/test_vcard.py          #  15  virtual card costs, both funding rails
```

The ledger is double entry. Money moves only through balanced postings and a payment is two legs with a suspense account in between. Seven failure modes can be injected, including a bank response lost after the debit already committed. The books balance after every one, and `cli.py audit` rebuilds each balance from the entries to prove it.

## What the simulation found

**A signature proves authorship, not honesty.** An inflated order whose lines genuinely add to Rs 600 was run past three signing designs. Agent signed, merchant signed, and both signed. All three settled it. What refused it was a per payment ceiling close to the real basket size. The protection comes from the limit the owner set.

**On UPI today, nobody is positioned to run the check.** A delegated payment produces four documents. The authority, the cart, the payment request and the settlement. Check A needs the cart and the request. Check B needs the cart and the authority. Every party on a UPI payment either never sees one of them or has a stake in the amount. The merchant holds the cart and earns more when the amount is higher. The remitter bank is disinterested and already decides whether to debit, and has never seen a cart. Adding one cart reference to the rail makes both checks enforceable by that bank.

Run `cli.py enforce` to see the whole table.

## Layout

```
src/identity.py       identities, the public and private split, signing
src/registration.py   the agent credential and revocation status
src/authority.py      what the owner allowed, and which rail can carry it
src/enforcement.py    who on a payment could run the check
src/consent.py        the order and the gate that binds a payment to it
src/policy.py         authority validation and the operator policy gate
src/agentic_token.py  the card rail, a scoped token the network checks
src/vcard.py          the agent virtual card and both funding sources
src/receipt.py        one signed record across both rails
src/core.py           money as integer paise, identifiers, response codes
src/models.py         domain objects and the transaction state machine
src/store.py          SQLite, the double entry ledger, idempotency
src/rails.py          banks, the switch, fault injection
src/recon.py          the reconciliation sweep and the ledger audit
src/orchestrator.py   the payment lifecycle
src/agent.py          the Claude planner and a deterministic fallback
src/bench.py          the browser test bench
src/console.py        the owner control app
src/cli.py            command line
src/api.py            FastAPI REST layer
```

## Standards used

The order check is the contribution. Everything under it is somebody else's specification, so a reviewer can check those parts against their own sources.

| Piece | Specification |
|---|---|
| Agent identifiers | [did:key](https://w3c-ccg.github.io/did-key-spec/) |
| Revocation status | [W3C Bitstring Status List](https://www.w3.org/TR/vc-bitstring-status-list/) |
| Signed artifacts | [RFC 8037](https://datatracker.ietf.org/doc/rfc8037/), EdDSA in JOSE |
| Key binding | [RFC 7800](https://datatracker.ietf.org/doc/rfc7800/), the `cnf` claim |
| Attestation shape | [RFC 9711](https://datatracker.ietf.org/doc/rfc9711/) EAT, [RFC 9334](https://datatracker.ietf.org/doc/rfc9334/) RATS |

## Honesty

Two things a reader should know up front.

The rails are simulated. Response codes carry a `SIM-` prefix so nobody mistakes them for real switch responses. The UPI figures come from secondary sources and stay unverified until the NPCI circulars are read.

The attestation is a stub. The token shape is a real Entity Attestation Token. The evidence behind it is not, because this runs on a laptop. Every attestation says `simulated: true`.

The full methodology, the results and the open questions are in [`docs/methodology-and-results.html`](docs/methodology-and-results.html). Claims there are marked `PRIMARY`, `SECONDARY`, `UNVERIFIED` or `CONTESTED`. Corrections to earlier work live in [`docs/research/corpus-corrections-2026-08.md`](docs/research/corpus-corrections-2026-08.md).
