# Agentic Payments — Verified Fact Base

**Compiled 7 August 2026.** Shared substrate for `agentic-commerce-india-research-report.md`
and `agentic-commerce-india-startup-strategy.md`. Every claim in those documents should trace
to a row here.

## Confidence markers

| Marker | Meaning |
|---|---|
| `PRIMARY` | Read from the issuing body's own document, or from ≥2 independent PSP developer docs that agree |
| `SECONDARY` | Reported consistently by credible trade press or vendor documentation; not read from the source instrument |
| `UNVERIFIED` | Single source, or inferred by contrast. **Do not cite externally without checking.** |
| `CONTESTED` | Sources actively disagree. Flagged in-line. |

---

## 1. UPI Reserve Pay (Single Block Multiple Debits)

Governing instruments: **UPI/OC/No. 200/FY 2024-25** (Jul 2024, enablement) and
**UPI/OC/No. 228/FY 2025-26** (Oct 2025, enhancement + rename to "Reserve Pay").

| # | Fact | Confidence | Note |
|---|---|---|---|
| 1.1 | Max block **₹10,000**, validity **up to 90 days** | `PRIMARY` | Cashfree and NPCI circular summaries agree |
| 1.2 | **One block per merchant, per customer** — *not* one block total | `SECONDARY` | **This corrects the corpus.** Multiple concurrent blocks across *different* merchants are permitted and expected |
| 1.3 | UPI apps **must** provide easy revoke access + consolidated view of all active blocks, merchant-wise | `SECONDARY` | **This corrects the corpus.** Circular-summary language |
| 1.4 | Customer **can** cancel the mandate directly from their UPI app | `PRIMARY` | Cashfree developer docs, explicit wording |
| 1.5 | Revocability may be **merchant-category dependent** — "irrevocable mandate availability depends on your merchant category" | `SECONDARY` | Cashfree. Important nuance: some categories get irrevocable blocks |
| 1.6 | Issuer banks **must** notify on block creation, modification, debit, revoke, expiry | `SECONDARY` | This is a *post*-debit notification, not a pre-debit veto window |
| 1.7 | **Pre-debit notification not required** | `UNVERIFIED` | ⚠️ Only inferred by contrast with Autopay's 24h PDN. No circular text found. **Was the corpus's single strongest argument — must be read in OC 228 before reuse** |
| 1.8 | No UPI PIN per debit; PIN only at block creation | `PRIMARY` | Cashfree + PayU agree |
| 1.9 | Failed debits retryable up to **3× in 24 hours** | `SECONDARY` | |
| 1.10 | Funding sources: savings, current, overdraft, RuPay credit card, pre-sanctioned credit line | `SECONDARY` | |
| 1.11 | Initially enabled for **verified online merchants, low-ticket high-frequency** | `SECONDARY` | Merchant eligibility is a real adoption constraint |
| 1.12 | Cashfree states limit as "₹10,000 **per month**, depending on merchant category, higher for secondary markets" | `CONTESTED` | Conflicts with per-block reading in 1.1. Resolve before any TAM math |
| 1.13 | Reconciliation via purpose code 77; ODR required; RBI TAT/compensation applies | `SECONDARY` | |

**Blocking action:** obtain OC 228 PDF via `npci.org.in/what-we-do/upi/circular` (direct fetch
returns HTTP 403). Resolve 1.7 and 1.12 before either report is cited externally.

## 2. RBI Authentication Directions, 2025

Ref **RBI/2025-26/79**, issued 25 Sep 2025, effective **1 April 2026**. Issued under s.18 r/w
s.10(2), PSS Act 2007.

| # | Fact | Confidence |
|---|---|---|
| 2.1 | Minimum two factors; for all non-card-present transactions at least one must be **dynamically generated and uniquely tied to that transaction**, or provable (biometric) | `SECONDARY` |
| 2.2 | Principle-based — SMS OTP no longer prescribed; issuers may offer a choice of factors | `SECONDARY` |
| 2.3 | Compromise of one factor must not affect the other | `SECONDARY` |
| 2.4 | **Exemptions include "recurring transactions under the e-mandate framework"** | `SECONDARY` |
| 2.5 | Other exemptions: small-value contactless card, gift PPIs | `SECONDARY` |
| 2.6 | Issuer must compensate customers for losses on non-compliant transactions | `SECONDARY` |
| 2.7 | Cross-border CNP rules for card issuers by 1 Oct 2026 | `SECONDARY` |

> ⚠️ **2.4 is the most consequential finding in this file.** The corpus and
> `thesis-problem-definition.md` assert that Reserve Pay / UPI mandates / agent payments are
> *not* on the exemption list, and build the "every agent debit is non-compliant, bank eats the
> loss" argument on that. But recurring e-mandate transactions **are** exempt. Whether Reserve
> Pay sits inside "the e-mandate framework" is now the crux, and it is a genuine interpretive
> question, not a settled fact. **The regulatory argument must be restated as conditional.**

## 3. UPI Circle

| # | Fact | Confidence |
|---|---|---|
| 3.1 | **Full delegation:** secondary user transacts independently, ~₹15,000/month cap, expiry up to 5 years | `SECONDARY` |
| 3.2 | **Partial delegation:** primary user approves each transaction with their own UPI PIN | `SECONDARY` |
| 3.3 | Security model assumes the delegate is a person with a device and a PIN | `PRIMARY` (structural) |
| 3.4 | UAP "builds on UPI Circle's delegated payments framework" | `SECONDARY` | Anonymous-sourced reporting only |

## 4. NPCI Unified Agent Protocol (UAP)

| # | Fact | Confidence |
|---|---|---|
| 4.1 | **Still proposed. Not launched.** No NPCI circular, no RBI approval published as of Aug 2026 | `SECONDARY` |
| 4.2 | Sourced to "four people aware of the development" (Business Standard, 8 Jul 2026) — anonymous | `SECONDARY` |
| 4.3 | Design: register, verify, authorise agents; verification layer *on top of* UPI, rails unchanged | `SECONDARY` |
| 4.4 | Builds on UPI Circle; incorporates spending limits and consent controls | `SECONDARY` |
| 4.5 | NPCI to maintain logs of agentic transactions | `SECONDARY` |
| 4.6 | RBI oversight expected, likely a **centralised registry of verified agents** | `SECONDARY` |
| 4.7 | Major Indian payment firms decided **against** building a rival protocol | `SECONDARY` |
| 4.8 | Industry participants explicitly name chargeback/dispute flows as a required piece | `SECONDARY` |
| 4.9 | Early use cases expected to be low-value high-frequency (groceries, bills) | `SECONDARY` |

**Implication:** the standards window the corpus banks on is still open, and 4.8 says the
dispute gap is recognised inside the consultation — which cuts both ways for Warrant Ledger.

## 5. Live agentic commerce in India

| # | Fact | Confidence | Note |
|---|---|---|---|
| 5.1 | **Swiggy** shipped MCP across Food, Instamart, Dineout — ChatGPT, Claude, Gemini; 40,000+ products | `SECONDARY` | Jan 2026 |
| 5.2 | **Swiggy AI-tool orders are cash-on-delivery only** | `SECONDARY` | ⚠️ Major finding — the agentic loop is **not closed**; no payment leg at all |
| 5.3 | Swiggy MCP requires ChatGPT **developer mode** + manual server URL + OTP login; not consumer-ready | `SECONDARY` | MediaNama hands-on test |
| 5.4 | **BigBasket** — first Indian conversational quick commerce on ChatGPT with **embedded UPI payment**, via Razorpay, using **Reserve Pay** | `SECONDARY` | This is the live reference implementation of the architecture under discussion |
| 5.5 | BigBasket flow: agent presents options → **single user confirmation** → order placed | `SECONDARY` | Human-present confirmation, i.e. Mode 0/1, not autonomous |
| 5.6 | Razorpay partnered with **NPCI and OpenAI** for UPI agentic payments in ChatGPT and Claude | `SECONDARY` | |
| 5.7 | Swiggy **Builders Club** (Apr 2026) — invite-only, 3 MCP servers, 18+ API tools | `SECONDARY` | |
| 5.8 | **Flipkart MCP: not found.** Named in one aggregator source, unconfirmed by any primary search | `UNVERIFIED` | Do not repeat the claim |
| 5.9 | Razorpay + NPCI agentic pilot on Reserve Pay (Zomato/Swiggy/Zepto), 20 Feb 2026 | `SECONDARY` | From existing corpus, not re-verified here |

## 6. Global protocol landscape

| # | Fact | Confidence |
|---|---|---|
| 6.1 | **AP2** — authorization layer. Intent Mandate (human-not-present) → Cart Mandate (human-present) → Payment Mandate. W3C Verifiable Credentials, not JWT/OAuth. Extension to A2A via Agent Card | `SECONDARY` |
| 6.2 | AP2 Intent Mandate scopes: seller, category, price ceiling, time window. Agent may generate the Cart Mandate itself **if the Intent Mandate's conditions are precisely met** | `SECONDARY` |
| 6.3 | **AP2 donated to the FIDO Alliance, 28 Apr 2026, v0.2** — now community governance | `SECONDARY` |
| 6.4 | **UCP** (Google + Shopify, NRF Jan 2026) — decentralised, merchant-hosted; uses AP2 for mandates; multiple payment methods | `SECONDARY` |
| 6.5 | **Shopify made UCP self-serve 17 Jun 2026** — any developer registers an agent profile, public MCP endpoint, no approval gate | `SECONDARY` |
| 6.6 | **ACP** (OpenAI + Stripe) — centralised, platform-mediated, Shared Payment Token, single payment method, Stripe lock-in. Beta | `SECONDARY` |
| 6.7 | Claimed take-rate gap ~3.2% (UCP) vs ~7.2% (ACP) | `UNVERIFIED` — vendor comparison, treat as marketing |
| 6.8 | **Adyen Agentic** (16 Jun 2026) — translator across UCP, ACP, AP2, Meta AI checkout | `SECONDARY` |
| 6.9 | **Visa TAP** — attests at the HTTP edge that an authorised agent is present | `SECONDARY` |
| 6.10 | **Mastercard Verifiable Intent** — binds issuer identity, user authorization, agent fulfilment into a credential chain for dispute adjudication | `SECONDARY` |
| 6.11 | **Stripe/Tempo Machine Payments Protocol** on mainnet; **x402** traction on Base | `SECONDARY` |
| 6.12 | Typical stack: ACP or UCP to transact, AP2 to authorize, TAP/Agent Pay at the rail, x402 at the edges | `SECONDARY` |

> **6.13 — the corroborating caveat, quoted:** *"An AP2 mandate verification only says the
> mandate covered the action, not that the action satisfied the obligation — the mandate
> constrains what the agent could do, not whether the agent did the right thing."*
> `SECONDARY`. This is independent third-party corroboration of the central thesis in the
> research report. It is stated there as a caveat and nowhere developed.

## 7. Academic prior art

| # | Work | Relevance | Confidence |
|---|---|---|---|
| 7.1 | `arXiv:2604.15367` — *SoK: Security of Autonomous LLM Agents in Agentic Commerce* | Names **"standardised authentication for instruction origin validation"** as an open gap. ⚠️ P1 is therefore no longer novel *as an observation* — the contribution must be a mechanism | `PRIMARY` (fetched) |
| 7.2 | `arXiv:2606.18005` — *LLM Consumer Behavior Theory* (Jun 2026) | Nearest prior work: agent–principal framing grounded in utility theory + behavioural economics; "agentic demand" | `SECONDARY` |
| 7.3 | `arXiv:2603.14864` — *Shopping Companion* / ShoppingBench | **Constraint violations ≈ 25% of SOTA agent failure modes.** Empirical anchor for mandate overreach. Multi-turn task success ≈ 35% | `SECONDARY` |
| 7.4 | `arXiv:2606.08790` — *RAILS: Verification-Native Clearing for Agentic Commerce* | Directly adjacent to the Warrant Interlock concept — **read before claiming novelty** | `SECONDARY` |
| 7.5 | `arXiv:2604.03976` — *Quantifying Trust: Financial Risk Management for Trustworthy AI Agents* | Directly addresses "can trust be measured" | `SECONDARY` |
| 7.6 | `arXiv:2510.25819` — *Identity Management for Agentic AI* | Authorization/authentication for agents | `SECONDARY` |
| 7.7 | Bettman, Luce & Payne (1998), *Constructive Consumer Choice Processes*, J. Consumer Research | The constructed-preference foundation | `PRIMARY` (canonical) |
| 7.8 | **No work found bridging constructed-preference theory to agent authorization scope** | The open niche. Searched Aug 2026: "constructed preference theory LLM shopping agents intent mandate authorization" and adjacent | `SECONDARY` — absence of evidence |

## 8. Scale context

| # | Fact | Confidence |
|---|---|---|
| 8.1 | UPI June 2026: **22.71 bn transactions, ₹28.92 tn**; 63.5% person-to-merchant | `SECONDARY` |
| 8.2 | ONDC: **200 mn+ cumulative transactions** by early 2026; positioned as an agentic rail but **no formal agentic specification found** | `SECONDARY` |
| 8.3 | Corpus cites UPI May 2026 at 23.2 bn — slightly above the June figure; monthly volumes fluctuate | `SECONDARY` |

## 9. Facts still unresolved

Ordered by how much they change the conclusions.

1. **OC 228 pre-debit notification wording** (1.7) — was the corpus's strongest argument
2. **Whether Reserve Pay falls inside "the e-mandate framework"** for RBI exemption (2.4) — determines whether the compliance market exists at all
3. **₹10,000 per block vs per month** (1.12) — changes all TAM arithmetic
4. **Whether any live Indian agentic flow is human-absent** — every confirmed flow (5.4, 5.5) has a human confirmation step
5. **Whether ONDC has any agentic work in progress** — searched, nothing surfaced; ask ONDC directly
6. **UAP's actual scope** — authorization only, or liability too (4.8 suggests disputes are in scope)

## Sources

- [NPCI UPI circulars](https://www.npci.org.in/what-we-do/upi/circular) · [OC 228 PDF](https://www.npci.org.in/uploads/UPI_OC_No_228_FY_2025_26_Enhancement_in_UPI_Single_Block_Multiple_Debits_UPI_Reserve_Pay_a9095c181d.pdf) (403 on direct fetch) · [OC 200 PDF](https://www.npci.org.in/PDF/npci/upi/circular/2024/UPI-OC-No-200-FY-24-25%E2%80%93Enablement-of-UPI-Mandate-feature-of-Single-Block-Multiple-Debits.pdf) · [Complinity summary of OC 228](https://complinity.com/legal-update/npci-issues-enhancements-in-upi-single-block-multiple-debits-upi-reserve-pay--20722/)
- [Cashfree Reserve Pay docs](https://www.cashfree.com/docs/payments/upi-reserve-pay/reserve-pay) · [PayU Reserve Pay docs](https://docs.payu.in/docs/upi-reserve-pay) · [Razorpay Reserve Pay](https://razorpay.com/blog/upi-reserve-pay/) · [BoxPay ReservePay](https://developers.boxpay.tech/docs/checkout-integration/upi-reservepay/)
- [RBI Authentication Directions 2025 — Khaitan analysis](https://www.khaitanco.com/thought-leadership/RBI-Authentication-Mechanisms-for-Digital-Payments-Transactions-Directions) · [Mondaq obligations summary](https://www.mondaq.com/india/new-technology/1728730/understanding-rbi-authentication-mechanisms-for-digital-payment-transactions-directions-2025-obligations-for-banks-nbfcs-and-payment-providers) · [KPMG note](https://kpmg.com/in/en/insights/2025/12/reserve-bank-of-india-rbi-authentication-mechanisms-for-digital-payment-transactions-directions-2025.html)
- [Business Standard — UAP](https://www.business-standard.com/finance/news/india-may-allow-agentic-ai-led-upi-transactions-under-new-npci-protocol-126070801343_1.html) · [Business Standard — how UAP may work](https://www.business-standard.com/finance/news/unified-agent-protocol-will-ai-be-making-upi-payments-for-you-now-here-s-how-it-may-work-126070900865_1.html) · [MediaNama — how NPCI should approach agentic payments](https://www.medianama.com/2026/07/223-npci-agentic-payments-upi/)
- [YourStory — Swiggy MCP](https://yourstory.com/2026/01/swiggy-lets-users-order-through-chatgpt-claude-gemini) · [Business Standard — Swiggy MCP](https://www.business-standard.com/companies/news/swiggy-enables-grocery-food-delivery-via-chatgpt-and-other-ai-tools-126012701092_1.html) · [MediaNama hands-on test](https://www.medianama.com/2026/01/223-ordering-chatgpt-swiggy-services-working/) · [Stellagent — India agentic commerce](https://stellagent.ai/insights/india-agentic-commerce-fintech-payment)
- [Stellagent — UCP vs ACP](https://stellagent.ai/insights/ucp-vs-acp-commerce-protocol-comparison) · [Stellagent — MCP/A2A/AP2/UCP/ACP](https://stellagent.ai/insights/mcp-vs-a2a-vs-ap2-protocol-comparison) · [DigitalApplied — standards guide](https://www.digitalapplied.com/blog/agentic-commerce-standards-ucp-acp-ap2-2026-merchant-guide) · [Adam Silva Consulting](https://www.adamsilvaconsulting.com/insights/agentic-commerce-protocols-ucp-acp-ap2)
- [arXiv:2604.15367 SoK](https://arxiv.org/pdf/2604.15367) · [arXiv:2606.18005](https://arxiv.org/pdf/2606.18005) · [arXiv:2603.14864](https://arxiv.org/pdf/2603.14864) · [arXiv:2606.08790 RAILS](https://arxiv.org/pdf/2606.08790) · [arXiv:2604.03976 Quantifying Trust](https://arxiv.org/pdf/2604.03976) · [arXiv:2510.25819](https://arxiv.org/pdf/2510.25819)
- [TechPolicy.Press — AI agents and India's DPI](https://www.techpolicy.press/ai-agents-and-the-next-layer-of-indias-digital-infrastructure/) · [MediaNama — India AI Impact Summit, KYA](https://www.medianama.com/2026/02/223-agentic-commerce-india-ai-impact-summit/)
