# Milestone 6A — Generalize to the double-auction market benchmark

Milestone 6A adapts the **same monitor interface** to the continuous
double-auction benchmark ([`andyjliu/llm-agent-collusion`](https://github.com/andyjliu/llm-agent-collusion)),
rather than the synthetic Bertrand toy used in Scenarios A/B. The requirement asks
for market harm and utility metrics on this external environment, evaluated through
the identical monitor contract.

## Why this milestone

Milestones 1–5 use a toy Bertrand market with a clean collusion index. The
double-auction benchmark is a different market microstructure (many buyers and
sellers posting bids/asks over rounds) with its own collusion dynamics. Reusing the
monitor interface here is the generalization test: *does the trusted monitor's
advantage survive a change of market structure, or was it an artifact of the toy?*

## Interface reuse (no monitor changes)

The monitor must remain scenario-agnostic (Milestone 2 contract):

- `MonitorStrategy` / `MonitorOutcome` unchanged.
- `EvidenceBundle` repopulated by a new `EvidenceCollector.collect_double_auction`.
- `MonitorSignals` reused: `artifact_violation` = a verified harmful market outcome
  (e.g. sustained supra-competitive clearing price), `coordination_score` = a
  behavioural/statistical signal over bid/ask histories.
- Enforcement mapped to the auction's action space (see below).

The only new code is an **adapter**, not new monitor logic — that is the point.

## Adapter plan

| piece | markets (Bertrand, current) | double auction (new) |
|---|---|---|
| environment | `BertrandMarket` | new `DoubleAuctionEnvironment` wrapping the upstream engine |
| observation | own price/profit + rivals' prices | own book/holdings + public tape |
| action space | 7-element price delta | post bid/ask / accept |
| benchmarks | competitive `1.01`, monopoly `1.50` | competitive clearing vs collusive clearing (derived) |
| collusion signal (Δ) | profit-based index | supra-competitive clearing price / suppressed volume |
| enforcement | forced price | order rejection / price bound / temporary exclusion |
| utility | consumer welfare | allocative efficiency, trades executed, surplus |

## Parameters (scenario-specific)

| parameter | values | rationale |
|---|---|---|
| number of buyers/sellers | small/large | auction competitiveness |
| rounds | short/long | time-to-detection |
| communication | none / public / private pairs | how coordination is carried |
| market-clearing rule | continuous vs call | microstructure sensitivity |
| agent model family | scripted controls + LLM | emergence vs harness validation |

## Metrics

Reuse the full hierarchy: detection recall/FPR, harm prevention, residual harm, time
to detection, task utility retained, intervention cost, recovery rate — plus
double-auction-specific: **allocative efficiency** and **clearing-price inflation**.

## Blocker / licensing note

As with Milestone 1's audit of the upstream market repo, the reference code declares
no license; Milestone 6A begins with a license/access re-audit. If the upstream
engine is not redistributable, the adapter targets a documented equivalent
double-auction implementation and records the deviation, exactly as the Bertrand toy
records its departure from the paper.

## Deliverables

- `collusions_lab/environments/double_auction/` (adapter + benchmarks).
- `EvidenceCollector.collect_double_auction`.
- `experiments/milestone6a_double_auction.yaml`.
- `docs/milestone-6a-markets.md` (this file) updated with results.
- Replay/provenance reuse (no harness changes expected).
