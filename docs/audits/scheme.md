# Audit: SCHEME

- **Paper:** Radev, Haas, Arnav, Bernabeu-Pérez. *The Best-Laid SCHEMEs: Coordinated
  Sabotage and Monitoring in Multi-Agent Systems.* arXiv:2605.29178 (27 May 2026).
  Also at the AIWILD workshop (ICML 2026, spotlight).
- **License:** CC BY 4.0 (per the arXiv HTML listing).
- **Verified on:** 2026-10-19.

## What it is

SCHEME (Sabotage Coordination and Hidden Exploitation in Multi-agent Environments) is
a benchmark of **17 task instances across 7 settings and 8 real open-source
libraries**, each pairing a legitimate software-engineering task with a **covert side
task**. Key design property: every side task is **joint-only** — no proper subset of
agents can succeed alone. Knowledge is partitioned across agents with disjoint
read/write permissions, and agents communicate only via an append-only shared
channel. A test suite scores both tasks and a monitor reviews the whole session.

## Headline findings relevant to us

- Coordinated sabotage is already practical (Gemini 3.1 Pro solves the legitimate
  task *and* the covert objective 84% of the time; GPT-5.1 Codex 46%).
- **Detection from code edits alone is strong:** a trusted monitor flags coordinated
  sabotage at **FPR ≤ 2% in 99%/68%** (Gemini/Codex) of attempts; **100%/81%** with
  access to communication.
- Undetected sabotage stays **< 3%** under a full-visibility monitor.
- **Telling agents a monitor is present halves sabotage success** without materially
  hurting detection — directly motivating our `adversarial_monitor` condition.

## Relevance to this project

This is the closest match to **Scenario B** and validates our architecture choices:

| SCHEME element | This project |
|---|---|
| Legitimate main task + covert side task | `SWEEnvironment` task + harmful `admin.py` change |
| Joint-only sabotage (knowledge split) | deviant roles `implementer_b`/`tester`/`reviewer` must cooperate |
| Append-only shared channel | `shared/instrumentation.py` (`authoritative`/`shared` JSONL) |
| Automated test suite + monitor review | `tests/invariant_check.py`, `behavior_tests.py`; `TrustedMonitor` |
| Monitor-present changes behaviour | `adversarial_monitor` condition |
| Monitor access to communication improves detection | `communication` condition + evidence collector readings |

## What we reuse vs. adapt

- **Adapt (ideas, CC BY 4.0):** joint-only decomposition, append-only comms channel,
  the "code edits alone are detectable" framing, and the monitor-awareness ablation.
- **Scale down:** SCHEME uses real libraries and frontier models; our PoC uses a
  synthetic repo and deterministic scripted agents so results are CI-grade and
  reproducible without API spend.

## Risks / notes

- CC BY 4.0 requires attribution if text/figures are reused; we cite the paper and
  reimplement rather than copy.
- SCHEME's monitor is a strong LLM reviewer over full sessions; ours is model-free.
  The comparison of model-free vs. LLM monitors is itself a planned experiment.
