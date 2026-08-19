# Agent Initiated Payments in India
## Problem definition


India is extending its payment system that was built entirely around human beings to AI Agents, which is not a human. Every safeguard in UPI comes from an assumption about how people behave. Two factor authentication, fraud scoring, pre debit notification, dispute reason codes, liability rules, all of them. Each of these assumptions fails when the payer is software. NPCI's Unified Agent Protocol proposes to solve this by extending UPI Circle, which is a delegation feature whose security depends on the delegate being a person with a phone and a PIN. An AI agent has neither. My MS Project proposal identifies the human assumptions the agentic payment stack quietly inherits, shows how each one fails under agent behaviour and under attack, and specifies what should replace them.

## What has changed recently

Between April 2025 and the middle of 2026, every major payment network shipped an agent protocol. Mastercard Agent Pay, Visa Intelligent Commerce and Trusted Agent Protocol, Google AP2, OpenAI with Stripe, and American Express. In India the sequence moved faster and matters more. Razorpay and NPCI put AI agents onto live UPI Reserve Pay on Swiggy, Zomato and Zepto in pilot mode in February 2026 . Pine Labs shipped its own agentic protocol P3P on UPI in June 2026. NPCI then began drafting the Unified Agent Protocol in consultation with the banks and industry.

The point to be made from all of this is simple. Every one of these protocols answers the question of how an agent gets permission to pay. Not one of them answers what happens when the agent holds valid permission and still does the wrong thing. Authorisation has been solved by these protocols but everything after authorisation is still an issue.

## The main problem

Core Idea of my project.

| # | What UPI assumes about the payer | What the assumption justifies | How an agent breaks it |
|---|---|---|---|
| A1 | The payer is present when the money moves | Two factor authentication, PIN at the transaction, device binding | The agent transacts unattended, from cloud infrastructure, hours or weeks after the PIN authorisation and mandate approval |
| A2 | The payer behaves like a person | Fraud scoring on time of day, velocity, device fingerprint, location | The agent at 3 AM doing 10 transactions a second with sudden surge in traffic, with no device and no touch. The current DPI may block this |
| A3 | Instructions come from the payer | One consent at mandate creation is treated as authority for everything afterwards | Prompt injection means the instruction may come from a poisoned web page and not from a person |
| A4 | The payer understands what they agreed to | Consent is treated as informed and specific | "Order my usual" is very underspecified, and every user phrases intent in their own way |
| A5 | The payer can step in before money moves | Pre debit notification, and revoking the mandate in the app | UPI Reserve Pay removes both of these by design, for speed |
| A6 | The payer is a legal person | Agency law, contract formation, liability allocation | An agent is not a person and cannot be an agent in law |
| A7 | A completed payment means a human decided | UDIR dispute reason codes assume either a human acted or the system failed | There is no reason code for "the agent misunderstood the instruction" |

The agentic payment stack is being built by extending current UPI mechanisms whose validity depends on assumptions that the agent violates, and the extension is happening without anyone stating those assumptions.

## Problem Classification

### P1. Instruction origin problem

There is exactly one strong authentication event in an agentic UPI payment. The user approves the mandate inside their bank app, on their registered device, using their UPI PIN. After that there is nothing. Every later debit is triggered by a sentence typed into a chat window, and that window has no PIN, no device binding to the mandate holder, and no way to check who typed it.

So the rail authenticates authorisation, meaning that somebody holding the PIN agreed to a spending limit. It does not authenticate instruction origin, meaning whether the person giving this particular instruction is the same person who set that limit. These are two different questions and only the first one is answered anywhere in the stack.

The ways this fails:

* A shared or unattended device, where a spouse, child, flatmate or colleague uses the logged in chat
* Account takeover on the agent platform. The chat account is protected by a password. The mandate was protected by a PIN bound to a device. The attacker only needs to break the weaker one
* Voice and ambient interfaces, where anyone in the room can speak and there is no speaker verification anywhere
* Prompt injection, Instructions are often hidden inside web pages, documents or search results on open web pages,... so that an agent reading them changes its behaviour. Attackers built pages optimised to be specifically found by agents to inject instructions. An agent that browses the open web while having a live payment mandate becomes an attackable target.
* A rogue or compromised agent operator, whose own systems generate the instruction
* A leaked mandate reference, A mandate reference is the unique ID that points to the pre-approved payment authorization which once escapes, behaves like a bearer credential. It means Whoever posses this Mandate ID can act if they are you, unless system requires additional authentication.


There is also an RBI rule that matters here, and it works against agent payments rather than in their favour.

The rule is the Authentication Directions, 2025. RBI issued it on 25 September 2025 and it applies from 1 April 2026.

**The rule says,** Every digital payment needs two separate proofs that the right person is paying. One of those two proofs must be freshly created for that one payment. A UPI PIN typed at the moment of paying is a good example of a fresh proof while a saved password is not.

RBI no longer forces banks to use SMS OTP. Banks can choose which proofs they use. So the type of proof is flexible. But the *number* is not. It stays at two with one of them fresh on every payment.

**Problem challenging this,** An AI agent pays when nobody is watching. There is no person sitting there to type a PIN. So the agent cannot produce a fresh proof for each payment, because it has nobody to get it from. While, RBI lists six kinds of payment that do not need the two proofs like Small contactless card taps, Repeat payments under the e mandate system, Some prepaid instruments, Toll payments, Small offline payments and Travel booked on corporate cards.

UPI mandates, Reserve Pay, UPI Circle, delegated payments and AI agents are not on that list.

**Section 9 of this circular:** It says that if a customer loses money on a payment that did not follow this rule, the bank must compensate them in full without argument.

So, If agent payments on Reserve Pay are not excused, then every one of them is happening in a way the rule does not permit, and the bank carries the full loss.

Source: [https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12898&Mode=0](https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12898&Mode=0)


### P2. Intent Fidelity problem: Did the agent buy what the human meant?

The mandate checks one thing, which is the amount. Nothing checks whether the purchase actually reflects the instruction. An agent buying 10kg of the wrong rice for ₹900 looks exactly the same to the rail as an agent buying the right rice for ₹900.

There are four sub problems here:

**Underspecification:** Natural language instructions are always incomplete. The user types,"Buy my usual evening groceries". Here, "My usual" has no referent the system can verify. Instruction style also varies from person to person, so the same phrase means different things for different users.

**When to ask:** When should the agent stop and ask a clarifying question? Every question adds friction. Every question not asked risks a wrong purchase. This is a cost of error problem and it is genuinely open.

**Price drift:** The price the human saw when consenting and the price at the debit are not the same. Surge pricing, delivery fees, expired coupons, items injected at the merchant page can happen and nothing in the flow compares the two numbers.

**Selection quality.** An agent choosing from ranked results on AI platforms inherits whatever that ranking is optimising for. If merchants start optimising for AI visibility instead of product quality, then the agent buys whatever is most readable to it rather than whatever is best. This is search engine optimisation happening again, but this new era is for Answer Engine Optimisation (AEO) against a buyer who lacks independent opinion.

### P3. Manipulation Problem: was the agent turned against its own principal?

An agent that browses the open web while holding a live payment mandate is an attackable target. This is the a new security class in the whole problem.

**Indirect prompt injection.** Instructions hidden inside web pages, documents and search results change how the agent behaves. Attackers have built pages designed specifically to be found by agents. An agent is the first financial actor whose instructions can be rewritten in the middle of a transaction by an attacker. A human buyer holding a company card does not get reprogrammed by reading a web page. How it can be detected earlier and can be prevented?

**Refund manipulation.** An agent can be pushed into triggering a refund when no real failure happened, which takes money from the merchant. The current Image generation tech can be used to do fraud in refund. It can also happen that user intentionally doesn't do it while an attacker manipulates the agent to do it.

**Merchant side attack on the UPI reserve.** A hostile merchant pulls the entire blocked pool in one go and disappears. Reserve Pay is built for multiple partial debits, so nothing about the pattern looks unusual.

**Endpoint authenticity.** How does the agent establish that the merchant it is dealing with is real? Fake storefronts are cheap to build, and an agent has no equivalent of the visual trust cues a human uses.

### P4. Evidence and accountability: can anyone prove what happened?

This section makes the other three matter.

**The reasoning gap.** An agent optimises for reaching a conclusion, which here means the payment went through. But what systems and processes did it bypass in order to arrive at that conclusion? The success is visible.

**The record gap.** A dispute needs proof of what the mandate was at the moment of the transaction, what the agent was told, what it did, and where those two diverged. No protocol specifies that record. UDIR's reason codes have no entry for an agent's mistake.

**The liability gap.** Nobody bears agent caused loss by law. A prompt injected payment is authorised but not intended. The mandate is valid, the credential is valid, and nothing was compromised. So it may not count as an "unauthorised transaction" under RBI's customer protection framework at all, which means those protections may never attach. The economic consequence is that no insurance market can form here, because there is no actuarial base to price against.

**Explainability for the person affected.** The agent is a black box. But the person who has to accept or dispute its decision is a consumer. An explanation that satisfies a model audit is not the same as an explanation that helps a user decide whether they were wronged.

## Context and constraints

**Privacy Policies:** An agent that shops for a user needs his shopping history, budgets, transaction history, merchant preferences, location and spending habits. Three questions have no published answer from any Indian provider. What reaches the LLM? What stays inside the PSP? What is shared with the merchant?

This cuts across all four sections and each of them therefore creates a DPDP obligation. 

**Who funds the trust layer:** UPI is zero Merchant Discount Rate (MDR), so there is no revenue on the rail, and one cannot show ads to an agent. The Standing Committee on Finance recommended bringing MDR back for large merchants in March 2026. Whether agentic transactions will carry a fee is unresolved, and it changes the economics for everybody.

**Merchant value:** Agentic commerce may destroy merchant value instead of creating it. Walmart withdrew ChatGPT Instant Checkout over roughly three times worse conversion. Merchant of record rules push agent errors onto merchants who did not cause them. Agent mediated selection also strips out merchandising, upselling and brand equity. Merchants carry the cost with no clear upside, so they adopt defensively because being invisible to agents is worse than adopting.

**Answer Engine Optimisation.** It is relevant to the selection quality problem in P2.

## Problem Prioritistion

**Instruction origin verification and decision time evidence for agent initiated payments on UPI.**

My reasons:

* P1 is genuinely new. Very little work exists on verifying that an agent's instruction came from its principal, and it is the problem holding the caps down.
* P4 is complementary of P1 and is directly linked to UAP.
* P2  sits inside a large and well funded NLP literature, and It will be compared against it.
* P3 is unsolved by everyone. It can be kept as the threat model that feeds P1, because injection is the reason instruction origin cannot be assumed.
## References

Technical and protocol level analysis of AP2, ACP, Visa TAP and P3P is needed to see what is already built and the design inputs for what UAP should specify.







