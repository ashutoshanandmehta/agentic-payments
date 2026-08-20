# Problem statement

**Written:** 19 Aug 2026
**Scope:** delegated payments. Not agentic commerce.

## Where my work starts

The cart is already full. Something else searched for products, compared prices, and
picked the shop. My work starts one step later, at the moment the agent tries to pay.

> **Is this agent allowed to make this payment, and can I prove it afterwards?**

Everything before the cart is out of scope.

## How UPI Reserve Pay works today

Reserve Pay is the closest thing UPI has to a delegated payment. Its formal name is
**Single Block Multiple Debits (SBMD)**. NPCI set the framework in Operating Circular
OC 200 (July 2024) and expanded it in OC 228 (October 2025).

The flow has three steps:

1. The customer approves one mandate in their UPI app.
2. Money is blocked in the customer's own account. It does not move yet.
3. The merchant debits against that blocked pool, **multiple times**, until the pool
   is empty or the mandate expires.

The limits, corrected against `../research/corpus-corrections-2026-08.md`:

- **₹10,000** maximum per block, **90 days** validity. `PRIMARY`
- **One block per merchant per customer.** A customer may hold blocks at several
  different shops at once, and UPI apps must show all of them in one view. `PRIMARY`
- About nine merchant categories are eligible: grocery, department stores, fast food,
  food stores, pharmacy, taxi, transport, EV charging, marketplaces. `SECONDARY`
- **No UPI PIN per debit.** There is one strong authentication event, at block
  creation. `PRIMARY`

That last point is the whole problem in one line. The human authenticates once, at
the start. Every debit after that is unauthenticated by the human.

## The gap

An agent does not know which shop it is paying until the cart is finished. But UPI
makes you name the shop when you create the block.

You can work around this by pre-blocking at every shop the agent might use. Three
shops means ₹30,000 of the customer's money locked up, and you must list the shops in
advance. So the honest statement of the gap is:

> **UPI has no single payment authority that can be spent across an open set of
> shops.** You can approximate it by naming the shops in advance and paying the
> capital cost, but you cannot express "spend up to ₹1,000 at whichever grocery shop
> turns out to be cheapest."

That is a payment-leg problem, and it is the centre of the thesis.

## What is missing at the moment of payment

The mandate checks the amount. Nothing checks meaning.

An agent buying 10kg of the wrong rice for ₹900 looks identical, to the rail, to an
agent buying the right rice for ₹900.

Two supporting claims from the earlier corpus were **corrected** and must not be
repeated as stated:

- *"There is no self-service revoke."* **Wrong.** OC 228 requires UPI apps to offer
  revocation and a consolidated view of active blocks. Whether every app actually
  implements it is an open empirical question, and some blocks may be issued
  irrevocable. The safeguard exists in the specification. `CONTESTED`
- *"There is no pre-debit notification."* **Unverified.** No circular text was found
  saying this. Banks *are* required to notify on block creation, modification, debit,
  revoke and expiry. So a debit notification exists; what may be absent is a *veto
  window before* the debit. The honest version is: the human learns after the money
  moved. `UNVERIFIED — read OC 228 directly before using this`

## What can go wrong, concretely

These follow from the mechanics above. Each is a scenario the simulation should model.

**Price drift.** The user agrees to a cart at ₹640. Between agreement and debit,
surge pricing and delivery fees push it to ₹810. The rail sees ₹810 is under the
limit and allows it. Nothing compares ₹810 to the ₹640 the human saw.

**Double debit.** The agent's request times out and it retries. Two debits, two
orders, one intent. Reserve Pay is *built* for multiple debits against one block, so
a second debit looks completely normal.

**Slow drain.** The block lives 90 days. By day 40 the user has forgotten it exists.
The agent, still authorised, keeps spending.

**Payee substitution.** The cart was agreed with shop A. The payment is routed to
shop B. Nothing at the payment boundary compares them.

**Wrong basket.** The user says "order my usual." The agent has two candidate carts
in memory and picks the wrong one. ₹1,400 of unwanted items, inside the ₹10,000 pool,
so it goes through.

## Who absorbs the loss today

Nobody has a settled answer, which is itself the finding.

NPCI's UDIR dispute system has reason codes for failed, unauthorised and fraudulent
transactions. It has **no code for "the agent misunderstood."** `SECONDARY`

Reported industry positions: Target treats agent purchases as customer-made, so the
customer eats a wrong-size or wrong-item order. Palo Alto Networks documented agents
being manipulated into issuing refunds to attackers. Chargebacks911 argues the
industry is building agentic commerce without dispute infrastructure at all.

## The open regulatory question

RBI's Authentication Mechanisms for Digital Payment Transactions Directions, 2025
exempt "recurring transactions under the e-mandate framework" from fresh
authentication.

**Does Reserve Pay sit inside that exemption?** If yes, agent debits against a block
are already compliant. If no, every one of them is non-compliant and the issuing bank
carries full liability under Section 9.

So far as I can find, neither RBI nor NPCI has addressed this publicly. `CONTESTED`

This is a better research question than a settled premise.

## What counts as a contribution

The observation that instruction origin goes unverified after mandate creation is
**no longer novel**. `arXiv:2604.15367` names it as open work.

So describing the gap is not a contribution. **Only a mechanism is.**

The mechanism I am proposing: three signed records at the payment boundary, and two
deterministic checks between them.

The three records:

1. **The payment authority.** Signed by the human, in advance. Who may spend, how
   much, at which shops, in which categories, until when.
2. **The cart.** What is being paid for, to whom, how much.
3. **The payment request.** The agent asking to execute.

The two checks:

- Does the payment request still match the cart? Nothing changed in between.
- Does the cart fit inside the authority? The agent stayed in bounds.

Both checks are arithmetic. No language model sits in the approval path, because a
bank cannot authorise a payment on a probability.

## The question I have not answered

**Who signs the cart?**

If the agent signs it, the agent can lie about what is in it. If the shop signs it,
the shop can lie about the price. If both sign it, neither can lie alone — but that
requires the shop to actively take part, which is a much larger assumption about the
world.

This decides what the system can actually prove. Everything else follows from it.

## Things to verify before this is submitted

- Read **NPCI OC 228** section by section. Two claims above depend on it and NPCI's
  site blocks automated fetching.
- Check whether **Juspay** has published an AP2-to-UPI binding. They are an AP2
  launch partner, Indian, and work on UPI. If they have, part of the novelty is gone.
- Find any RBI or NPCI statement on the e-mandate exemption question.

## Appendix: the agent virtual card

An alternative design routes the money through a card the agent controls: the user's
mandate funds the card, and the card pays the merchant. Implemented in `src/vcard.py`
and measured in `tests/test_vcard.py`.

It is worth stating what the simulation showed, because the result is not obvious from
the design:

**Putting a credential between the user and the merchant destroys merchant scoping.**
The mandate can only name the payee it actually pays, and that payee is the card. So a
mandate scoped to one shop becomes a mandate scoped to one card, and the card is
unscoped. The test demonstrates a payment reaching a merchant that the same mandate
refuses when paid directly.

Two further costs: float strands on the card when a spend fails and no reconciliation
sweep looks there, and the load transaction never names the merchant, so the rails
cannot link a spend to the load that funded it.

None of this makes the design wrong. It makes the design *expensive*, and the price is
paid in exactly the property this thesis is about — the ability to say afterwards what
the user authorised.
