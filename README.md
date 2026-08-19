# Agentic Payments — Trust Infrastructure for Delegated Spend

Research, product and thesis work on **identity, authorisation and audit for AI agents that
spend money** — with India / UPI as the primary rail.

**Author:** Ashutosh Anand · BS-MS Y22, IIT Kanpur
**Supervisor:** Prof. Vimal Kumar, IITK
**Status:** pre-build. Research corpus + protocol design. Nothing shipped yet.
**Last major revision:** 19 Aug 2026

---

## The one-line problem

> Every money system ever built assumes the transactor is a human.

When an AI agent spends, five questions have no answer: which agent is this, whose is it, what
was it allowed to spend, is it behaving normally, and — when it goes wrong — what's the proof.
The first three must be answered *before* the payment, because a limit is enforced at
authorisation, not in hindsight.

The industry name for this is **KYA — Know Your Agent**.

## What I am doing

Two tracks, deliberately split. They share primitives; they do not share a timeline.

| | **Thesis / standards track** | **Company track** |
|---|---|---|
| Horizon | The future rail (UAP, AP2) | The present rail (cards, existing mandates) |
| Mode | Simulation, protocol design, publication | Design partners, pricing discovery |
| Bet | Consumer delegated payments arrive | Businesses already run agents that spend |
| Success | Publishable contribution; a seat in the UAP consultation | 2 paid design partners |

The split exists because [`docs/pitch/UAP.md`](docs/pitch/UAP.md) slide 7 declined the consumer
bet explicitly — *"a bet on two futures and we're not taking it"* — while its own kicker notes
*"the same primitives become the consumer UAP layer when the rail opens."* Both are true. The
error would be funding the company off the future bet, or starving the thesis of the future work.

## The two novel claims

Neither is in the pitch deck yet. Both are the thesis track's contribution.

1. **The AP2↔UPI binding is unwritten.** Google's AP2 (Sept 2025, 60+ partners) defines
   Intent / Cart / Payment Mandates as signed W3C Verifiable Credentials and names UPI as a
   target rail with defined extension points — but it is card/pull-first and ships no UPI
   extension. `SECONDARY` · prior-art check pending on Juspay, an AP2 launch partner.

2. **The delta between a signed Intent Mandate and a signed Cart Mandate is decision drift,
   and it is cryptographically measurable.** The payments industry frames agent safety as spend
   caps — *did it stay under the limit*. Drift is the harder question — *did it buy the thing
   you meant*.

### The rail-level gap that motivates both

UPI today has **no primitive for a budget delegated to an agent and spendable across merchants.**
UPI Autopay is fixed-payee with a mandatory 24h pre-debit notification. UPI Reserve Pay is one
block *per merchant*. Both bind a payee at mandate creation — before a comparison agent has
decided anything. See [`docs/research/assumptions-forward-2026-08.md`](docs/research/assumptions-forward-2026-08.md) A3.

## Repository map

```
docs/
├── thesis/     the research contribution
│   ├── thesis-problem-definition.md
│   └── why-agent-identity.md
├── research/   the evidence base — and its corrections
│   ├── agentic-commerce-india-research-report.md    market + regulatory landscape
│   ├── agentic-payments-fact-base-2026-08.md        verified present facts
│   ├── corpus-corrections-2026-08.md                past claims that were wrong
│   └── assumptions-forward-2026-08.md               forward bets + falsifiers
├── product/    what gets built and sold
│   ├── warrant-interlock-product-document.md
│   ├── agentic-commerce-india-startup-strategy.md
│   └── agentic-payments-product-research-and-decks.md
└── pitch/      how it is argued
    ├── UAP.md                                       the 12-slide deck + appendices
    ├── mentor-pitch.md · mentor-pitch-v2-*.md
    └── objection-we-already-scope-agents.md         the hard objection, rehearsed
```

## Evidence discipline

Load-bearing claims carry a confidence marker. This is not decoration — it is the standard the
corpus is held to.

| Marker | Means |
|---|---|
| `PRIMARY` | Verified against the source document or a direct test |
| `SECONDARY` | Reported by a credible third party, not verified at source |
| `UNVERIFIED` | Believed, not checked — do not build on it |
| `CONTESTED` | Sources disagree, or the claim was checked and failed |

Two files enforce it in both directions. `corpus-corrections-2026-08.md` audits claims already
made — on 7 Aug 2026 it killed three load-bearing facts behind the original Reserve Pay wedge.
`assumptions-forward-2026-08.md` does the same for claims about a future that hasn't arrived:
each assumption gets a falsifier and a "what survives if false" line.

**A finding that kills a good argument still gets written down.** That's what the corrections
file is for.

## Not in this repo

- `shopping-agent/` — the Aug 2026 UPI shopping-agent demo. Its own git repo, contains live
  credentials, deliberately kept separate.
- GLP-1 healthtech work, exporter-scraping scripts — unrelated projects that shared a folder.

## Where to start reading

1. [`docs/pitch/UAP.md`](docs/pitch/UAP.md) — the whole argument in 12 slides. Slides 6 and 7 are the persuasive core.
2. [`docs/research/assumptions-forward-2026-08.md`](docs/research/assumptions-forward-2026-08.md) — what this is betting on, and what would kill it.
3. [`ROADMAP.md`](ROADMAP.md) — what happens next.
