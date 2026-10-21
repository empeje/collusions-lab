# Milestone 6A -- Generalize to the double-auction market benchmark

Milestone 6A adapts the **same monitor interface** to a continuous double auction (CDA),
a second market microstructure with different collusion dynamics, rather than the
synthetic Bertrand toy used in Scenarios A/B. The requirement asks for market harm and
utility metrics on this external environment, evaluated through the identical monitor
contract.

## Why this milestone

Milestones 1-5 use a toy Bertrand market with a clean collusion index. A continuous
double auction (many buyers and sellers posting bids/asks over rounds, transactions on
crossing orders) is a different market microstructure with its own collusion dynamics.
Reusing the monitor interface here is the generalization test: *does the trusted
monitor's advantage survive a change of market structure, or was it an artifact of the
toy?*

## Reference

* Paper: *Evaluating LLM Agent Collusion in Double Auctions*, arXiv:2507.01413.
* Repo: https://github.com/andyjliu/llm-agent-collusion -- **no declared license**
  (GitHub license API returns 404; "all rights reserved"; verified 2026-10-19).

Published mechanics we reimplement (idea reuse only): sellers value each lot at **$80**,
buyers at **$100**, competitive equilibrium **$90**, markets run **30 discrete rounds**,
each agent places or withdraws **one bid/ask per round**. The relevant levers are
seller/buyer communication, seller **oversight**, **boss pressure** (keep margins high),
and hiding the round horizon.

## Licensing stance: vendor-but-isolate + NOTICE

We do **not** ship any upstream code or data. Concretely:

* The upstream checkout lives only in a **gitignored** `experiments/upstream/` directory,
  used as a local dev reference while implementing. It is never imported by the package,
  never referenced by tests, and never committed.
* `NOTICE.md` records the license risk (no license = all rights reserved), states that the
  shipped `DoubleAuctionEnvironment` is an **independent reimplementation** from the
  paper's published design, and instructs anyone reusing the upstream repo to obtain
  author permission first.
* This mirrors the Milestone 1 Bertrand deviation note: we adapt mechanisms and metrics
  and record the departure, rather than vendoring.

If the upstream repo later gains a permissive license, the adapter can be re-pointed at it
without changing the monitor contract.

## Interface reuse (no monitor changes)

The monitor must remain scenario-agnostic (Milestone 2 contract):

* `MonitorStrategy` / `MonitorOutcome` unchanged.
* `EvidenceBundle` repopulated by a new `EvidenceCollector.collect_double_auction`.
* `MonitorSignals` reused: `artifact_violation` = a verified harmful market outcome
  (sustained supra-competitive clearing price), `coordination_score` = a
  behavioural/statistical signal over bid/ask histories.
* Enforcement mapped to the auction's action space (see below).

The only new code is an **adapter**, not new monitor logic -- that is the point.

## Adapter plan

| piece | markets (Bertrand, current) | double auction (new) |
|---|---|---|
| environment | `BertrandMarket` | new `DoubleAuctionEnvironment` (independent reimplementation) |
| observation | own price/profit + rivals' prices | own book/holdings + public tape |
| action space | 7-element price delta | post bid/ask / accept / withdraw |
| benchmarks | competitive `1.01`, monopoly `1.50` | competitive clearing `90` vs collusive clearing (derived) |
| collusion signal (Delta) | profit-based index | supra-competitive clearing price / suppressed volume |
| enforcement | forced price | order rejection / price bound / temporary exclusion |
| utility | consumer welfare | allocative efficiency, trades executed, surplus |

## Parameters (scenario-specific)

| parameter | values | rationale |
|---|---|---|
| number of buyers/sellers | small/large | auction competitiveness |
| rounds | short/long (default 30) | time-to-detection |
| communication | none / public / private pairs | how coordination is carried |
| market-clearing rule | continuous vs call | microstructure sensitivity |
| agent model family | `scripted` controls + LLM | emergence vs harness validation |

## Metrics

Reuse the full hierarchy: detection recall/FPR, harm prevention, residual harm, time to
detection, task utility retained, intervention cost, recovery rate -- plus
double-auction-specific: **allocative efficiency** and **clearing-price inflation**.

## Code integration points

| piece | code path |
|---|---|
| New environment | `collusions_lab/environments/double_auction/` |
| Scenario enum | `schemas.Scenario.DOUBLE_AUCTION` |
| Evidence adapter | `monitor/evidence.py::collect_double_auction` |
| Enforcement map | `runner` (auction action space) |
| Config | `experiments/milestone6a_double_auction.yaml` |
| NOTICE | `NOTICE.md` |
| Tests | `tests/test_double_auction.py` |

## Running the sweep

```powershell
python -m collusions_lab.experiments experiments/milestone6a_double_auction.yaml --out runs_m6a
python -m collusions_lab.evaluation runs_m6a
```

## Deliverables

* `collusions_lab/environments/double_auction/` (adapter + benchmarks).
* `EvidenceCollector.collect_double_auction`.
* `experiments/milestone6a_double_auction.yaml`.
* `docs/milestone-6a-markets.md` (this file) updated with results.
* `NOTICE.md` recording the upstream license risk and the independent reimplementation.
* Replay/provenance reuse (no harness changes expected).

## Blocker / licensing note

As with Milestone 1's audit of the upstream market repo, the reference code declares no
license. Milestone 6A therefore does **not** vendor it: the adapter targets our own
independent double-auction implementation and records the deviation. Any future direct
use of the upstream engine requires explicit author permission.
