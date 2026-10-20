# Requirements traceability

Maps requirements in the user-supplied `collusions-requirements.md` to this
repository. A repo audit or conceptual adaptation is not counted as benchmark
reproduction. Status: **Done** (implemented and checked), **Partial** (a scoped
prototype), **Planned** (later milestone), **Gap** (required outcome not present).

## Section 1 — Two scenarios with meaningful harm

| Requirement | Implementation | Status | Tests |
|---|---|---|---|
| Scenario A: multi-agent market manipulation, coordinated price inflation | `environments/markets/bertrand.py` (`BertrandMarket`, `MarketConfig`) | Partial (synthetic toy) | `tests/test_market_env.py` |
| Scenario B: SWE collusion — suppress defects, mislead tests, defeat checks | `environments/software_engineering/{synthetic_repo,swe_env}.py` | Partial (synthetic toy) | `tests/test_swe_env.py` |
| Retain prices/bids/profit/welfare (A) and diffs/tests/specs (B) | `shared/instrumentation.py` JSONL streams; `result.json` | Done | `tests/test_episodes.py::test_episode_writes_audit_trail` |

## Section 2 — Existing research to build on

| Requirement | Implementation | Status |
|---|---|---|
| Review relevant repos (SCHEME, NARCBench, LLM-agent-collusion, algorithmic pricing) | `docs/audits/*.md` | Done (review only) |
| NARCBench activation-probe integration | Audited in `docs/audits/narcbench.md`; no probe integrated because the published setup needs model activations and high-VRAM extraction | Planned (separate white-box track) |
| Reproduce a software-engineering benchmark baseline (SCHEME or equivalent) | Paired synthetic fallback sweep in `experiments/milestone1_swe.yaml`; SCHEME task/code artifacts are not linked from the project page | Fallback done; upstream reproduction blocked |
| Reproduce a market benchmark baseline (double-auction collusion or equivalent) | Paired synthetic fallback sweep in `experiments/milestone1_market.yaml`; reference code/data are not integrated because no license is declared | Fallback done; upstream reproduction blocked |
| Base market design on the pricing-collusion paper | Selected mechanisms/metrics adapted in `bertrand.py`; not a replication; model deviation in `docs/architecture.md` | Partial |

## Section 3 — What the trusted agent does

| Requirement | Implementation | Status | Tests |
|---|---|---|---|
| Trusted decision-support component, not a peer LLM | `monitor/trusted_monitor.py`; model-free `Detector` + `MonitorPolicy` | Done | `tests/test_monitor.py` |
| Agents must not know the monitor exists | monitor log `visible_to_agents=False`; `Event`/`EpisodeRecorder` | Done | `tests/test_schemas.py` |
| Monitor log visible only to monitor; read access to agents' logs | separate `monitor.jsonl`; collector reads authoritative log | Done | `tests/test_episodes.py` |
| Action vocabulary: Allow / Hold / Constrain / Record evidence | `schemas.MonitorAction`; every `MonitorDecision` recorded | Done | `tests/test_monitor.py` |
| Model-free first version | no model calls in `monitor/` | Done | — |
| Observe independently (not agent summaries) | `monitor/evidence.py::EvidenceCollector` re-runs checks | Done | `tests/test_swe_env.py` |
| Detect coordination and consequences | coordination signal + market Δ; `monitor/detector.py` | Done | `tests/test_monitor.py` |
| Verify before intervening (independent tests / diff / provenance; market controls) | `env.claimed_vs_independent`, `invariant_violated`, `provenance_complete`; market Δ vs benchmarks | Done | `tests/test_swe_env.py`, `tests/test_market_env.py` |
| Intervene minimally / graduated response | `monitor/enforcement.py` (HOLD vs CONSTRAIN vs forced price/release block) | Done | `tests/test_monitor.py` |
| Block unsafe release permanently until a human reviews a fixed agent | `run_episode` latches `CONSTRAIN`; `ReleaseGate` refuses bypass | Done | `tests/test_episodes.py`, `tests/test_swe_env.py` |
| Suspicious agreement alone must not penalize | policy: coordination → HOLD only | Done | `tests/test_monitor.py::test_market_coordination_alone_does_not_constrain` |
| Kill/purge an agent that discovers the monitor | **Resolved to quarantine, not purge** (append-only authoritative trail). `QUARANTINE` action + `QuarantineStore` | Partial — intentional deviation | `tests/test_monitor.py` (vocabulary), `shared/quarantine.py` |

## Section 4 — Distinguish collusion from coincidence

| Requirement | Implementation | Status | Tests |
|---|---|---|---|
| Three separate labels (benign convergence / harmful tacit / explicit) | `schemas.GroundTruthLabel`; `runner._label_market`, `_label_swe` | Done | `tests/test_episodes.py` |
| Five matched conditions | `schemas.EpisodeCondition` | Done | `tests/test_schemas.py` |
| Independent baseline / shared-context / communication / known-collusion / adversarial-monitor | Market information and public-message access vary by condition; SWE prior messages are included for LLM prompts | Partial; scripted agents do not generate messages | `tests/test_experiments.py`, `tests/test_episodes.py` |
| Randomized seeds, model configs, held-out tasks | seeds + provider/model in YAML (multi-model sweeps are milestone 5) | Partial | `tests/test_experiments.py` |

## Section 5 — Measuring whether it works

| Metric | Implementation | Status | Tests |
|---|---|---|---|
| Collusion detection recall | `evaluation/detection_metrics.py::detection_recall` | Done | `tests/test_evaluation.py` |
| False-positive rate | `false_positive_rate` | Done | `tests/test_evaluation.py` |
| Harm prevention rate | `evaluation/harm_metrics.py::harm_prevention_rate` | Done | `tests/test_evaluation.py` |
| Residual harm | `residual_harm` | Done | `tests/test_evaluation.py` |
| Time to detection | `detection_latency` | Done | `tests/test_evaluation.py` |
| Task utility retained | `evaluation/utility_metrics.py::task_utility_retained` (paired on/off) | Done | `tests/test_evaluation.py` |
| Intervention cost | `intervention_cost` | Done | `tests/test_evaluation.py` |
| Recovery rate | `recovery_rate` | Done | `tests/test_evaluation.py` |
| Detection and prevention measured separately | `evaluate()` report splits both | Done | `tests/test_evaluation.py::test_evaluate_report_structure` |
| Prevention–utility trade-off, confidence intervals across episodes | paired seeds supported; CI/multi-run aggregation | Planned (milestone 5) | — |

## Section 6 — Small practical PoC, then expand

| Requirement | Implementation | Status |
|---|---|---|
| Representative structure (`environments/`, `agents/`, `monitor/`, logs, `shared services/`, `experiments/`, `evaluation/`, `tests/`, README) | repository layout | Done |
| Petri for model-based behavioral audits | `docs/petri-inspect.md`; package/task smoke-launched locally, but the small model never interacted with the target | Partial; needs a capable auditor model |
| Inspect AI for reproducible evaluation runs | `inspect_tasks/collusions_eval.py`; optional `.[inspect]` dependency; CLI smoke runs completed | Done for deterministic harness adapter |
| Scenario A then Scenario B | both implemented | Done |
| Expand to robustness/ablations/cross-model (milestone 5) | — | Planned |
| Generalize monitor interface to double-auction benchmark (milestone 6) | — | Planned |

## Section 7 — When the trusted agent fails

| Failure mode | Where handled |
|---|---|
| False positives from legitimate teamwork | bounded by shared-context/communication controls + FPR metric |
| Monitor lag / late intervention | `detection_latency`; latching CONSTRAIN |
| Blocking for non-collusion reasons | detection and prevention reported separately (`evaluate`) |
| Agents that discover the monitor | `QUARANTINE` + `QuarantineStore` |

See `docs/architecture.md` for the full threat model and limitations.
