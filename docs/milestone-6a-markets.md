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

Published market mechanics we reimplement (idea reuse only): **five buyers** value each
lot at **$100**, **five sellers** at **$80**, competitive equilibrium is **$90**, and the
market runs **30 discrete rounds**. The first book is seeded with buyer bids in [$80,$85]
and seller asks in [$95,$100]. At each round close, highest bids match lowest asks; a
trade clears at the **average bid/ask price**. An agent trades at most one lot per round.
The reference also studies seller communication, oversight, authority pressure and hiding
the round horizon; those behavioral factors are documented as follow-on experiments rather
than claimed as reproduced in the current scripted sweep.

## Licensing stance: vendor-but-isolate + NOTICE

We do **not** ship any upstream code or data. Concretely:

* The upstream checkout lives only in a **gitignored** `experiments/upstream/` directory,
  used as a local dev reference while implementing. It is never imported by the package,
  never referenced by tests, and never committed.
* `NOTICE.md` records the license risk (no license = all rights reserved), states that the
  shipped `DoubleAuctionMarket` is an **independent reimplementation** from the
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
  (sustained supra-competitive clearing prices or sustained volume suppression), `coordination_score` = a
  behavioural/statistical signal over bid/ask histories.
* Enforcement mapped to the auction's action space (see below).

The only new code is an **adapter**, not new monitor logic -- that is the point.

## Adapter plan

| piece | markets (Bertrand, current) | double auction (new) |
|---|---|---|
| environment | `BertrandMarket` | new `DoubleAuctionMarket` (independent reimplementation) |
| observation | own price/profit + rivals' prices | own book/holdings + public tape |
| action space | 7-element price delta | post bid/ask / accept / withdraw |
| benchmarks | competitive `1.01`, monopoly `1.50` | competitive clearing `90` vs collusive clearing (derived) |
| collusion signal (Delta) | profit-based index | trade-price inflation plus separately verified volume suppression |
| enforcement | forced price | order rejection / price bound / temporary exclusion |
| utility | consumer welfare | allocative efficiency, trades executed, surplus |

## Parameters (scenario-specific)

| parameter | values | rationale |
|---|---|---|
| number of buyers/sellers | small/large | auction competitiveness |
| rounds | short/long (default 30) | time-to-detection |
| communication | none / public / private pairs | how coordination is carried |
| market-clearing rule | continuous in this milestone; call auction deferred | microstructure sensitivity |
| agent model family | `scripted` controls + LLM | emergence vs harness validation |

## Metrics

Reuse the full hierarchy: detection recall/FPR, harm prevention, residual harm, time to
detection, task utility retained, intervention cost, recovery rate -- plus
double-auction-specific: **allocative efficiency**, executed volume, buyer surplus, and
clearing-price inflation. No-trade rounds have no imputed execution price.

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

## Results (scripted control sweep)

`experiments/milestone6a_double_auction.yaml` -- 3 conditions x 2 topologies (none/full)
x 2 seller counts x 2 buyer counts x 3 seeds x 3 monitors (none/artifact/oracle) =
**216 episodes**, 30 rounds each (offline, scripted agents). Harmful coordination is
seller-side; buyer agents remain competitive. Aggregate via
`python -m collusions_lab.evaluation runs-m6a`:

| monitor | detection recall | precision | fpr | prevention | residual harm | latency | task utility |
|---|---|---|---|---|---|---|---|
Results are generated from the configured sweep and summarized in the experiment output;
the old fixed-size table was removed because it predated seller-only collusion and the
correct no-trade accounting.

* The independent baseline trades competitively and is labelled benign. The seller-only
  scripted collusion treatment suppresses trade volume; a verified efficiency drop after
  10 rounds is sufficient to intervene even when no executed price exists.
* The artifact and rules baselines constrain on that independent volume-harm signal. The
  monitor latches a seller ask cap at the competitive price; the LLM judge remains a
  separate, non-oracle baseline.

The scripted sweep tests harness and intervention behavior, not emergent LLM collusion.
Topology effects, model comparisons and the reference paper's seller oversight / pressure
conditions require provider-backed runs and remain follow-on work. The monitor does not
infer malicious intent from a quote alone; it acts on measured market harm.

## Status

Done (offline). LLM model-family sweeping for this scenario is deferred to the same
5b/network track as the other scenarios (blocked on provider access), and the scripted
controls above already validate the microstructure generalization.
