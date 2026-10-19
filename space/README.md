---
title: Collusions Lab
emoji: 🕵️
colorFrom: indigo
colorTo: red
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: apache-2.0
short_description: Trusted-monitor benchmark for harmful multi-agent collusion
---

# Collusions Lab — interactive demo

An **intervention benchmark** for detecting and disrupting harmful multi-agent
coordination. The demo runs one matched episode and shows the ground-truth label,
monitor decisions, harm metrics, and (for markets) the mean-price trajectory.

Two scenarios share one trusted monitor:

- **Markets** — repeated Bertrand price competition. Harm = sustained
  supra-competitive prices.
- **Software engineering** — a six-agent pipeline over a synthetic repo. Harm = a
  coordinated change that defeats the authorization check and reaches release.

Conditions: `independent_baseline`, `shared_context`, `communication`,
`known_collusion`, `adversarial_monitor`. Toggle **Monitor enabled** to compare
monitor-on vs monitor-off outcomes.

## Providers

- `scripted` — deterministic, CPU, no token. Default and CI-grade.
- `mock` — offline canned responses.
- `hf` — HF Inference API; requires an `HF_TOKEN` Space secret.
- `local` — open-weight model via `transformers`, routed through ZeroGPU when
  available on this Space.

Ground truth is evaluation-only and is never shown to the monitor. See the
[main repository](https://github.com) for the architecture, metric definitions, and
the requirements traceability.

Full project source, tests, and docs: this Space ships a copy of the `collusions_lab`
package; the canonical repository holds `docs/`, `experiments/`, and `tests/`.
