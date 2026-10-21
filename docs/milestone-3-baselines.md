# Milestone 3 -- Three monitor baselines

Milestone 3 turns the single trusted monitor into a **matched comparison of three
monitoring designs plus a no-monitor control**, so that any reduction in harm can be
attributed to the monitoring approach rather than to the environment or the agents.

The requirement is explicit: detection must be scored **separately** from
prevention, and the baselines must be *plausible* -- not strawmen. Each arm sees the
same episodes; only the monitor changes.

## The arms

| `monitor_type`  | Baseline        | What it does                                                                 |
|-----------------|-----------------|------------------------------------------------------------------------------|
| `none`          | Baseline 0      | No monitor. Natural incidence of harmful coordination.                       |
| `rules`         | Baseline 1      | **Surface heuristics only.** Regex/keyword coordination cues, approval-without-evidence, price-level thresholds. **No independent re-execution.** |
| `llm_judge`     | Baseline 2      | A **separate model class** classifies a *sanitized* evidence bundle and returns structured JSON. Threshold is calibrated on a validation split. |
| `artifact`      | Treatment       | **Independent artifact/evidence verification**: the monitor re-inspects the environment (invariant re-check, independent test execution, provenance completeness) and drives safety from that. Coordination is an **investigation flag only**. |

The `rules` arm intentionally trusts the pre-computed signal bundle, whereas the
`artifact` arm grounds its decisions in checks it performs itself. This is the
distinction the paper attributes to robust monitoring.

## Detection vs prevention

Each `MonitorDecision` records:

* `action` -- ALLOW / HOLD / CONSTRAIN / QUARANTINE (the *enforcement* effect),
* `flagged` -- whether the monitor raised a detection flag on this step,
* `monitor_type`, `detection_only`.

`detection_only: true` runs the full detection path but **suppresses enforcement**,
so a monitor that detects but does not act can be scored against one that acts. The
evaluation reports a `prevention_confusion` cell `prevented_without_flag` to surface
"prevented but never detected" cases (e.g. enforcement that fired for an unrelated
reason).

## Calibration (LLM judge)

`collusions_lab.monitor.calibrate_threshold(judge, validation, target_fpr)` sweeps
candidate thresholds over a labelled validation set and returns the threshold that
meets a false-positive budget with the highest recall. `calibrate_curve` returns the
full FPR/recall curve for reporting. The current experiment runner does not yet
automatically construct this validation set or apply the returned threshold to a
separate scored sweep; `judge_threshold` in YAML is currently a manually supplied
value. The split labels in the example YAML are metadata only.

The judge **fails safe**: any provider error or unparseable response becomes HOLD
rather than ALLOW. The judge input is allow-listed and stripped of ground-truth /
hidden-objective keys, so it cannot cheat by seeing the labels.

## Running the sweep

```powershell
# Offline (mock judge) smoke run -- exercises every arm without network:
python -m collusions_lab.experiments experiments/milestone3_baselines.yaml --out runs

# Real judge + real agents require the optional HF dependency and a token:
pip install -e ".[hf]"
$env:HF_TOKEN = "hf_..."
python -m collusions_lab.experiments experiments/milestone3_baselines.yaml --out runs
python -m collusions_lab.experiments experiments/milestone3_baselines_swe.yaml --out runs
python -m collusions_lab.evaluation runs
```

`experiments/milestone3_baselines.yaml` and
`experiments/milestone3_baselines_swe.yaml` cover the market and software
engineering environments respectively, replicating every `(condition, seed)` cell
across all four arms. The current runner accepts these matched sweeps, but it does
not automatically construct a validation set or apply a calibrated judge threshold;
the YAML threshold is manually supplied. Threshold calibration remains a manual
library workflow through `calibrate_threshold`.

## HF provider setup

The judge defaults to `hf` / `Qwen/Qwen2.5-3B-Instruct`. That provider needs the
`huggingface_hub` package (install `.[hf]`) and an `HF_TOKEN` environment variable.
CI stays offline: tests inject a `MockProvider(responder=...)` into the judge.

> **Account note.** On the current account, HF Inference Providers return
> `402 Payment Required` ("no remaining credits; subscribe to PRO"). The `hf` code
> path itself is exercised and correct -- it authenticates, forms the chat-completion
> request, and on any transport error the judge **fails safe to HOLD** (verified live).
> For a real judge without credits, use `judge_provider: ollama` with a local model
> (e.g. `qwen2.5:3b-instruct`), or `judge_provider: mock` for an offline smoke run.

## Reporting

`evaluate()` now emits, in addition to `overall` / `by_scenario`:

* `by_monitor_type` -- detection/harm/utility broken down per arm, with the
  `prevention_confusion` cells.
* `threat_curve` -- checks whether each arm's observed operating point meets fixed
  false-positive budgets (1%, 2%). It does not estimate a threshold curve; use
  `calibrate_curve` with validation scores for that.
