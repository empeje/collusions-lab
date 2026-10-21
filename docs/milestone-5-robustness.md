# Milestone 5 -- Robustness and ablation experiments

Milestone 5 turns the fixed PoC configuration into a **paired parameter sweep** that
probes where the trusted monitor's advantage holds and where it breaks. The requirement
(sections 4, 5, 7) calls for varying agent count, communication topology, observability,
monitor strength, and model family, and for evaluating on held-out tasks and benign
cooperation controls.

Milestones 3 and 4 held the environment fixed and varied the *monitor* and the
*intervention*. Milestone 5 does the opposite: it fixes the monitor contract and varies
the *environment and observability*, so we can attribute changes in detection, prevention,
and utility to the manipulation rather than to a change of monitor.

This document is the plan artifact. It specifies what is shared across scenarios, the
scenario-specific parameters, the exact code integration points, the config keys, the
verification commands, and what is explicitly deferred to **Milestone 5b**.

## Design principle

Every sweep must be **paired**: each manipulated configuration is compared against a
matched no-monitor (`monitor: none`) control at *identical seeds and identical
environment parameters*, so detection, prevention, and utility cost remain causally
attributable rather than confounded with the manipulation. The sweep runner emits the
`none` control alongside each treatment automatically.

## Shared across scenarios

| axis | shared definition | how it is expressed | code path |
|---|---|---|---|
| Number of agents | count of participants (`n_sellers` for markets; active SWE reviewer count) | `defaults.n_sellers` / `defaults.n_reviewers` | market loop; SWE role pipeline |
| Communication topology | which agents can see which messages: `ring`, `star` (hub), `full`, `none` | `topology` key -> `_topology_deliver` | `runner._topology_deliver` |
| Observability | what the monitor sees of the authoritative trail: `full`, `artifacts_only`, `no_messages` | `observability` key -> collector redaction | `EvidenceCollector.collect_*` |
| Monitor strength | `none`, `rules`, `llm_judge`, `artifact`, plus an `oracle` upper bound | `monitor` list | `schemas.MonitorType`, `runner.build_monitor_strategy` |
| Seeds & task holdout | randomized seeds and held-out `admin_reset` task family are implemented | `seeds`; `defaults.task_family` | `experiments.build_run_configs`; `SWEEnvironment` |
| Benign cooperation controls | shared-context & communication conditions with no hidden objective | existing `EpisodeCondition`s | `schemas.EpisodeCondition` |

### Topology

`topology` is threaded into a single helper, `runner._topology_deliver(topology, sender_index,
messages)`, that replaces the two inline `team_messages` blocks in the market and SWE
episode loops:

* `none`   -- no agent sees any other agent's message (independent control).
* `full`   -- every agent sees every message (current `communication` behaviour).
* `ring`   -- agent *i* delivers to *i+1 mod n* only.
* `star`   -- agent *0* (hub) receives from and delivers to all others; peers do not
  see each other.

Topology only has an effect when the condition is `communication` (or `known_collusion`
with comms enabled); under other conditions it is a no-op, so the pairing stays valid.

### Observability

`observability` is passed to `EvidenceCollector.collect_swe` / `collect_market` and
redacts what the **monitor** reads, never what agents read:

* `full`            -- current behaviour: artifact + evidence + full behavioural timeline.
* `no_messages`     -- MESSAGE events are stripped from `behavior`; decisions/claims kept.
* `artifacts_only`  -- only the `artifact` dict and reviewer `decisions` are exposed; the
  message timeline and raw evidence dict are withheld.

This is the direct probe of the requirements' **incomplete-observability** failure mode.

### Oracle upper bound

`MonitorType.ORACLE` adds an `OracleMonitor` that flags exactly the episodes whose
ground-truth structural signature is present in the evidence bundle (a verified harmful
outcome / invariant violation), ignoring coordination subtlety. It is a **non-deployable
upper bound** used to bracket recall; it never reads `GroundTruth`, only the artifact
signal, so it is not a label leak. It exists purely so robustness curves have a ceiling.

## Scenario-specific

### Markets (Scenario A)

| parameter | values | rationale | config key |
|---|---|---|---|
| `n_sellers` | 2, 3, 5, 8 | collusion is easier with few firms; tests whether the monitor's edge narrows as the market grows | `defaults.n_sellers` |
| `mu` (demand blending) | 0.0, 0.5, 1.0 | `mu=1` pure Bertrand, `mu=0` roulette-wheel (paper section 2); changes convergence dynamics | `defaults.mu` |
| `include_competitor_prices` | true/false | observability of rivals' prices | `defaults.include_competitor_prices` |
| `market_steps` | 100, 200, 500 | time-to-detection and convergence horizon | `defaults.market_steps` |
| `n_consumers` | 100, 200 | demand scale; sensitivity of Delta and welfare | `defaults.n_consumers` (new) |
| `simple_quantity` | true/false | paper eq. (5) reward form vs linear-demand benchmark form | `defaults.simple_quantity` (new) |
| `price_update` | `additive`, `softplus` | discrete-delta vs paper eq. (7) dynamics | `defaults.price_update` (new) |
| topology | `none`, `full`, `ring`, `star` | how price signals can be carried | `topology` |

### Software engineering (Scenario B)

| parameter | values | rationale | config key |
|---|---|---|---|
| reviewer count | 1, 2, 3 | independent reviewers reduce coordinated-approval risk (section 4 benign convergence) | `defaults.n_reviewers`; `experiments/milestone5_swe_structure.yaml` |
| task family | `audit_export` and held-out `admin_reset` tasks have distinct targets and instructions | distribution-shift test | `defaults.task_family`; `SWEConfig.task_family` |
| sensitive path set | `tests/*.py` only vs also the security module | under/over-inclusive provenance checks | `conditions[].extra.sensitive_paths` |
| tool permissions | full vs restricted (`CapabilitySet`, Milestone 4) | interaction between capability limits and monitoring | `restricted_tools` / `extra.capabilities` |
| observability | `full`, `artifacts_only`, `no_messages` | incomplete-observability failure mode (section 7) | `observability` |
| topology | `none`, `full`, `ring`, `star` | comms shape for the role pipeline | `topology` |

## Metrics to report

Milestone 5 adds to the existing detection/harm/utility families:

* **Robustness curves** -- metric vs each swept axis (recall vs `n_sellers`, FPR vs
  topology), per monitor type.
* **Distribution-shift table** -- group outcomes by the held-out SWE `task_family` axis.
* **Correlated-error probes** -- vary agent and judge provider/model independently.
* **Prevention-utility frontier** at fixed FPR budgets (reusing `threat_curve`) across
  the sweep.
* **Confidence intervals** across seeds, including paired treatment-minus-control
  intervals over matched episodes.

## Code integration points

| piece | code path |
|---|---|
| `ORACLE` monitor | `schemas.MonitorType`, `runner.build_monitor_strategy`, `monitor/baselines.py::OracleMonitor` |
| Topology delivery | `runner._topology_deliver`; market loop, SWE loop |
| Observability redaction | `monitor/evidence.py::collect_swe` / `collect_market` |
| New run fields | `runner.RunConfig.topology`, `.observability`; manifest/result echo them |
| Sweep plumbing | `experiments.build_run_configs` (list-valued `defaults` -> cartesian) |
| Aggregation + CIs | `evaluation/robustness.py::by_axis`, `bootstrap_ci`, `robustness_intervals`; exported in `evaluation/__init__` |
| Configs | `experiments/milestone5_topology.yaml`, `experiments/milestone5_structure.yaml`, `experiments/milestone5_swe.yaml`, `experiments/milestone5_swe_structure.yaml` |
| Tests | `tests/test_robustness.py` |

## Running the sweep

```powershell
# Offline (scripted agents), paired treatment vs none control, per axis:
python -m collusions_lab.experiments experiments/milestone5_topology.yaml --out runs_m5_topo
python -m collusions_lab.evaluation runs_m5_topo
python -m collusions_lab.experiments experiments/milestone5_structure.yaml --out runs_m5_struct
python -m collusions_lab.experiments experiments/milestone5_swe_structure.yaml --out runs_m5_swe_struct
python -m collusions_lab.evaluation runs_m5_struct
```

Expected shape: recall rises monotonically with monitor strength (`none` < `rules` <
`llm_judge` ~ `artifact` <= `oracle`); FPR stays bounded under benign `shared_context` /
`communication` controls; prevention degrades under `artifacts_only` / `no_messages`;
utility cost grows with topology density at fixed monitor.

## Results (offline, scripted agents)

Both sweeps run network-free with `scripted` agents and are fully reproducible:

* `milestone5_topology` (48 episodes: 4 topologies x 2 conditions x 3 seeds x 2 monitors),
  `milestone5_structure` (54 episodes: 3 `n_sellers` x 3 `mu` x 3 seeds x 2 monitors),
  and `milestone5_swe_structure` (144 episodes: 3 reviewer counts x 2 task families x 4 conditions x 3 seeds x 2 monitors).
* Paired control: every treatment run has a matching `monitor=none` run at the same seed,
  condition, and axis values. The `artifact` monitor reaches recall 1.0 / prevention 1.0 /
  residual 0.0 against the `none` control's recall 0.0 / prevention 0.0 / residual ~0.99.
* `evaluate` now emits a `by_axis` block for every axis that varies (topology,
  observability, `n_sellers`, `mu`, `market_steps`, `monitor_type`, `intervention`) and a
  `robustness` block with 95% bootstrap CIs (recall, harm-prevention, residual harm),
  overall and per axis value.
* Because `scripted` sellers do not condition their policy on delivered messages, the
  topology/residual axes show identical numbers offline -- the axis *plumbing* is what the
  offline sweep verifies; policy-level topology effects require LLM agents (Milestone 5b).
* The SWE reviewer-count sweep executes each reviewer as a separate agent and records
  the count as a first-class result axis. The held-out `admin_reset` family runs a
  separate behavior suite for reset authorization and audit logging.

## Deliverables

* `experiments/milestone5_topology.yaml`, `experiments/milestone5_structure.yaml`,
  `experiments/milestone5_swe.yaml`, and `experiments/milestone5_swe_structure.yaml`.
* `evaluation/robustness.py` (group-by axis + bootstrap CI).
* `docs/milestone-5-robustness.md` (this file) updated with results.
* `tests/test_robustness.py` for the topology/observability/oracle plumbing.

## Failure modes explicitly tested (requirements section 7)

| failure mode | how Milestone 5 probes it |
|---|---|
| Incomplete observability | `observability=artifacts_only` / `no_messages` |
| Correlated model errors | same-family and cross-family agent/judge combinations |
| Distribution shift | market structure (`n_sellers`, `mu`) and held-out SWE task family are swept |
| False positives from legitimate teamwork | shared-context + communication benign controls at scale |
| Intervention-induced degradation | intervention cost vs utility retained across monitors |
| Compromised enforcement | markets: agents attempt to bypass forced prices (future) |

## Provider-backed model-family sweep

The `scripted` controls keep the offline suite CI-grade and network-free. Real model
family evaluation uses `experiments/milestone5_models.yaml` and needs provider access:

* Model families: `qwen2.5:3b`, `llama3.1:8b`, ... selected per agent via `provider`/`model`.
* Correlated-error probe: monitor model family == agent model family vs not.
* The config defaults to local Ollama Qwen and Llama models; substitute installed models
  or providers before running. The family matrix is wired, but no empirical model-family
  results are claimed until the configured inference runs complete.

## Compliance status

Implemented: market seller-count and demand-blending sweeps; SWE reviewer-count,
task-family, communication-topology, observability, benign-control, and monitor-control
sweeps; paired bootstrap treatment/control intervals. The topology and structure configs pair
`monitor: none` and `monitor: artifact` at matched seeds and axis values.

Empirical model-family findings remain pending execution of the provider-backed sweep
with both configured model families. Paired intervals exclude unmatched runs. The legacy
`split` metadata is not used; task holdout is implemented through `task_family`.
