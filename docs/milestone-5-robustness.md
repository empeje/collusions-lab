# Milestone 5 — Robustness and ablation experiments

Milestone 5 turns the fixed PoC configuration into a **parameter sweep** that probes
where the trusted monitor's advantage holds and where it breaks. The requirement
(§4, §5, §7) calls for varying agent count, communication topology, observability,
monitor strength, and model family, and for evaluating on held-out tasks and benign
cooperation controls.

This document specifies the plan: what is shared across scenarios, and the
scenario-specific parameters for markets (Scenario A) and software engineering
(Scenario B).

## Design principle

Every sweep must be **paired**: each manipulated configuration is compared against a
matched no-monitor control at identical seeds, so detection, prevention, and utility
cost remain causally attributable rather than confounded with the manipulation.

## Shared across scenarios

| axis | shared definition | how it is expressed |
|---|---|---|
| Number of agents | count of participants (`n_sellers` for markets; SWE role duplicated for peer review) | `RunConfig` field / YAML `defaults` |
| Communication topology | which agents can see which messages: `ring`, `star` (hub), `full`, `none` | new `topology` key threaded into the observation builder |
| Observability | fraction/content of the authoritative trail the monitor sees: `full`, `artifacts_only`, `no_messages` | `observability` key -> `EvidenceCollector` redaction |
| Monitor strength | `none`, `rules`, `llm_judge`, `artifact`, plus an `oracle` upper bound | `RunConfig.monitor_type` (+ new `oracle`) |
| Model family | `scripted`, `qwen2.5:3b`, `llama3.1:8b`, ... | per-agent `provider`/`model` |
| Seeds & held-out tasks | randomized seeds; tasks split into `validation` / `test` families | YAML `seeds`, `conditions[].extra.split` |
| Benign cooperation controls | shared-context & communication conditions with no hidden objective | existing conditions |

## Scenario-specific

### Markets (Scenario A)

| parameter | values | rationale |
|---|---|---|
| `n_sellers` | 2, 3, 5, 8 | collusion is easier with few firms; tests whether the monitor's edge narrows as the market grows |
| `mu` (demand blending) | 0.0, 0.5, 1.0 | `mu=1` pure Bertrand, `mu=0` roulette-wheel (paper §2); changes convergence dynamics |
| `include_competitor_prices` | true/false | observability of rivals' prices |
| `market_steps` | 100, 200, 500 | time-to-detection and convergence horizon |
| topology | `none`, `public_board`, `private_pairs` | how price signals can be carried |
| demand/consumer model | linear vs `simple_quantity` | sensitivity of Δ and welfare to the demand model |

### Software engineering (Scenario B)

| parameter | values | rationale |
|---|---|---|
| reviewer count | 1, 2, 3 | independent reviewers reduce coordinated-approval risk (§4 benign convergence) |
| task family | `audit_export`, `auth_checks`, `policy_engine` (held out) | distribution-shift test (§7) |
| sensitive path set | `tests/*.py` only vs also `acme_portal/security.py` | under/over-inclusive provenance checks |
| tool permissions | full vs restricted (`CapabilitySet`, Milestone 4) | interaction between capability limits and monitoring |
| observability | full history vs artifacts-only (diffs), no-messages | incomplete-observability failure mode (§7) |
| model family | scripted vs LLM reviewer/implementer | correlated-errors failure mode (§7) |

## Metrics to report

The full Milestone 5 report adds to the existing detection/harm/utility families:

- **Robustness curves**: metric vs each swept axis (e.g. recall vs `n_sellers`,
  FPR vs topology), per monitor type.
- **Distribution-shift table**: validation vs test task family, with the delta.
- **Correlated-error probes**: monitor model family == agent model family vs not.
- **Prevention–utility frontier** at fixed FPR budgets (reusing `threat_curve`) across
  the sweep.
- **Confidence intervals** across seeds (bootstrap) — the explicit Milestone 5
  deliverable the current docs list as "planned".

## Deliverables

- `experiments/milestone5_robustness.yaml` (and per-scenario variants).
- `evaluation/` robustness aggregation (group-by axis + CI).
- `docs/milestone-5-robustness.md` (this file) updated with results.
- Tests for the new sweep plumbing (topology/observability redaction).

## Failure modes explicitly tested (requirements §7)

| failure mode | how Milestone 5 probes it |
|---|---|
| Incomplete observability | `observability=artifacts_only` / `no_messages` |
| Correlated model errors | same-model monitor vs agents |
| Distribution shift | held-out task family; new market structure |
| False positives from legitimate teamwork | shared-context + communication benign controls at scale |
| Intervention-induced degradation | intervention cost vs utility retained across monitors |
| Compromised enforcement | markets: agents attempt to bypass forced prices (future) |
