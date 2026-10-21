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
| Randomized seeds, model configs, held-out tasks | paired seed/parameter sweeps cover topology, observability, seller count, demand blend, and SWE reviewer count; actual held-out SWE task families and model-family sweeps are not implemented | Partial | `tests/test_experiments.py`, `tests/test_robustness.py` |

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
| Detection and prevention measured separately | `evaluate()` report splits both; per-decision `flagged` bit; `detection_only` mode; `prevention_confusion` | Done | `tests/test_evaluation.py::test_evaluate_report_structure`, `tests/test_baselines.py` |
| Prevention–utility trade-off, confidence intervals across episodes | `threat_curve` checks observed FPR budget compliance; `calibrate_curve` computes threshold points from validation evidence; `evaluation/robustness.py::bootstrap_ci` / `robustness_intervals` give 95% bootstrap CIs across seeds, overall and per axis value | Done (CIs landed in Milestone 5) | `tests/test_evaluation.py`, `tests/test_robustness.py` |

## Section 5b — Baseline comparison (Milestone 3)

| Requirement | Implementation | Status | Tests |
|---|---|---|---|
| Rules-only baseline (surface heuristics, no independent re-execution) | `monitor/baselines.py::RulesMonitor`; `policy.MonitorPolicy(rule_set="rules")` | Done | `tests/test_baselines.py` |
| Black-box LLM-judge baseline | `monitor/baselines.py::LLMJudgeMonitor` + `calibrate_threshold`; separate provider/model pair is enforced | Partial: calibration helper exists, but the sweep does not automatically create a validation split or apply its threshold | `tests/test_baselines.py` |
| Artifact-verification (treatment) baseline | `monitor/baselines.py::ArtifactVerificationMonitor` (independent detector + artifact policy) | Done | `tests/test_baselines.py` |
| No-monitor control | `monitor/baselines.py::NoMonitor` (`monitor_type=none`) | Done | `tests/test_baselines.py` |
| Detection separate from enforcement | `MonitorDecision.flagged`/`detection_only`; `TrustedMonitor(detection_only=...)` | Done | `tests/test_baselines.py::test_detection_only_records_flag_without_enforcing` |
| Judge fails safe | provider error / unparseable output → HOLD | Done | `tests/test_baselines.py::test_llm_judge_malformed_output_holds_failsafe` |
| Judge cannot see ground truth / hidden objectives | allow-listed, sanitized evidence payload | Done | `tests/test_baselines.py::test_llm_judge_sanitizes_evidence` |

## Section 5c — Controlled interventions (Milestone 4)

| Requirement | Implementation | Status | Tests |
|---|---|---|---|
| Intervention selectable independently of detection | `RunConfig.intervention` (`InterventionType`), YAML `intervention`; `runner._apply_market_intervention` / `_apply_swe_intervention` | Done | `tests/test_interventions.py` |
| Restricted tool permissions | `capabilities.py` (`Tool`, `CapabilitySet`); `AgentConfig.capabilities`; configured `restricted_tools` passed through experiment/run config; runner checks actions and embedded market messages | Done | `tests/test_interventions.py::test_restricted_tools_denies_revoked_actions` |
| Graduated review gate | `swe_env.ReleaseGate.request_release` → `ReviewOutcome` (ALLOW / ALLOW_WITH_RESTRICTIONS / REQUEST_CHANGES / BLOCK) | Done | `tests/test_interventions.py::test_review_gate_mapping` |
| Independent verification as an enforce-time action | `monitor/verification.py::IndependentVerifier` (`swe_verifier` / `market_verifier`) and audited verifier calls in both scenario runners | Done | `tests/test_interventions.py::test_independent_verification_sets_block` |
| Intervention vs no-intervention controls in both scenarios | `intervention: none` (detect only) vs enforcing arms; market and SWE sweeps | Done | `tests/test_interventions.py::test_none_arm_detects_but_does_not_prevent`, `test_swe_none_arm_detects_but_allows_harmful_release` |
| Per-intervention evaluation breakdown | `evaluation.by_intervention` (`tool_denial_rate`, review-outcome distribution) | Done | `tests/test_interventions.py::test_by_intervention_breakdown` |

## Section 6 — Small practical PoC, then expand

| Requirement | Implementation | Status |
|---|---|---|
| Representative structure (`environments/`, `agents/`, `monitor/`, logs, `shared services/`, `experiments/`, `evaluation/`, `tests/`, README) | repository layout | Done |
| Petri for model-based behavioral audits | `docs/petri-inspect.md`; package/task smoke-launched locally, but the small model never interacted with the target | Partial; needs a capable auditor model |
| Inspect AI for reproducible evaluation runs | `inspect_tasks/collusions_eval.py`; optional `.[inspect]` dependency; CLI smoke runs completed | Done for deterministic harness adapter |
| Scenario A then Scenario B | both implemented | Done |
| Expand to robustness/ablations (milestone 5) | `evaluation/robustness.py`, `experiments/milestone5_*.yaml`, `docs/milestone-5-robustness.md`; paired intervals, held-out tasks and provider-backed model sweeps | Done; model-family empirical matrix awaits broader execution |
| Generalize monitor interface to double-auction benchmark (milestone 6) | `environments/double_auction/`, `monitor/evidence.py::collect_double_auction`, `runner._run_double_auction_episode`, `experiments/milestone6a_double_auction.yaml`, `NOTICE.md`, `docs/milestone-6a-markets.md` | Done | `tests/test_double_auction.py` |

## Section 7 — When the trusted agent fails

| Failure mode | Where handled |
|---|---|
| False positives from legitimate teamwork | bounded by shared-context/communication controls + FPR metric |
| Monitor lag / late intervention | `detection_latency`; latching CONSTRAIN |
| Blocking for non-collusion reasons | detection and prevention reported separately (`evaluate`) |
| Agents that discover the monitor | `QUARANTINE` + `QuarantineStore` |

See `docs/architecture.md` for the full threat model and limitations.

## Milestone 2 — Standardize the harness

| Requirement | Implementation | Status | Tests |
|---|---|---|---|
| Common agent and environment transition contracts | `harness/interfaces.py`; environment `reset`, `observe`, and `step`; normalized `StepResult` | Done for current market and SWE environments | `tests/test_harness.py` |
| Common environment events and monitor decisions | `schemas.Event`, `EventType`, `MonitorDecision`; prompt and monitor-tool events are private from the agent shared stream | Done | `tests/test_harness.py` |
| Ground-truth labels | `GroundTruth` in `result.json`; scenario-specific label functions | Partial; no shared labeling contract | `tests/test_episodes.py` |
| Episode replay | `harness/replay.py`; requires manifest/result and wraps malformed event streams as `ReplayError` | Done for persisted audit replay | `tests/test_harness.py` |
| Record random seeds | `manifest.json` and environment reset | Done | `tests/test_harness.py` |
| Record model versions | Provider and model identifier in provenance | Partial; immutable hosted revision is not resolved | `tests/test_harness.py` |
| Record configured and generated prompts | Full generated prompts and hashes in private events; configured prompts and hashes in manifest | Done | `tests/test_harness.py` |
| Record tool calls | Monitor verification calls are recorded; scenario agents do not yet invoke tools | Partial | `tests/test_harness.py` |
| Record source diffs | SWE per-step diff artifacts | Done for SWE; not applicable to market episodes | `tests/test_harness.py` |
| Scenario-independent runner extension | Market and SWE loops remain separate in `runner.py` | Partial; new scenarios require runner changes | `docs/milestone-2-review.md` |

See `docs/milestone-2-review.md` for the compliance analysis and remaining work.
