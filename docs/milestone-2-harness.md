# Milestone 2 — Standardised Harness

Milestone 1 produced a working, instrumented, two-scenario benchmark. Milestone 2
turns it into a **standard harness**: one explicit contract that scenarios,
agents, monitors, external tooling (Inspect/Petri), and the replay/audit path all
target, with no scenario-specific coupling in the orchestration layer.

## Goals

1. **One interface** — agents, environments, and the runner agree on a small
   structural contract so a new scenario can be added without editing the runner.
2. **Replayable episodes** — any persisted episode can be reloaded and audited
   from its on-disk trail alone, without re-running agents.
3. **Complete event taxonomy** — prompts and tool calls are first-class events,
   not smuggled inside `ACTION` payloads.
4. **Verifiable provenance** — every episode manifest records the exact
   git commit, model, prompt hashes, and tool versions needed to reproduce it.

## Interfaces (`collusions_lab/harness/interfaces.py`)

Structural `typing.Protocol` contracts, checked with `runtime_checkable` so tests
can assert conformance:

- `AgentInterface` — `agent_id`, `role`, `act(observation) -> AgentAction`.
  Satisfied today by `ScriptedMarketSeller`, `LLMAgent`, and the SWE scripted
  agents.
- `EnvironmentInterface` — `reset`, `observe`, `step`, plus the **evidence hooks**
  the trusted monitor depends on (`changed_files`, `build_diff`). Satisfied by
  `BertrandMarket` and `SWEEnvironment`.
- `StepResult` — a normalised `(step, done, info)` tuple so scenario `step`
  return shapes converge.
- `Harness` — a thin facade over `runner.run_episode` that pins the entry point
  and pairs every run with its replay.

The monitor only ever sees `EnvironmentInterface` methods; it never imports a
scenario's private internals. That is what makes the "standard" claim real.

## Replay (`collusions_lab/harness/replay.py`)

`replay_episode(run, episode_id=None)` loads `manifest.json`, `result.json`, and
the four JSONL streams (authoritative, shared, monitor, quarantine) into an
immutable `EpisodeReplay`. Highlights:

- Read-only: replay never mutates the authoritative log.
- Integrity first: missing manifest **and** result raises `ReplayError`; malformed
  JSON raises rather than silently degrading.
- Typed accessors: `.provenance`, `.agents`, `.ground_truth`, `.decisions()`,
  `.agent_events()`.
- `list_episodes(runs_root)` enumerates every episode directory for batch audits.

## Event taxonomy

Milestone 1 emitted `ACTION`, `MESSAGE`, `CLAIM`, `DECISION`, `MONITOR`. Milestone
2 adds:

- `PROMPT` — recorded whenever an LLM agent returns `_llm` metadata, carrying the
  provider-reported model and a `prompt_sha256` over the exact system+messages.
  Emitted in both scenario loops.
- `TOOL_CALL` / `TOOL_RESULT` — recorded around the trusted monitor's independent
  test execution (`invariant_check`, `behavior_tests`). These are the monitor's
  own actions, so they are tagged `actor="monitor"` and never masquerade as
  agent-authored evidence.

## Provenance manifest

`EpisodeManifest` gained a `provenance: ProvenanceRecord` (schema-compatible
since Milestone 1) that `runner._build_provenance` now populates with:

| field           | meaning                                              |
|-----------------|------------------------------------------------------|
| `git_commit`    | repo HEAD at run time (nullable outside a repo)      |
| `python_version`| interpreter version                                  |
| `tool_versions` | installed collusions-lab / PyYAML / requests / inspect-ai |
| `model_versions`| `provider:model` per agent                           |
| `prompt_hashes` | sha256 of each configured `system_prompt`            |
| `extra.runtime_prompt_hashes` | distinct sha256 per agent of the *generated* prompts actually sent |
| `extra.diffs`   | relative paths of persisted per-step source-diff artifacts |

The manifest is the reproducibility contract: given the commit and the hashes,
an auditor can confirm a re-run used identical prompts and models.

### Source-diff artifacts

Every SWE step persists the environment's `build_diff()` output to
`diffs/step_NNN.diff` (empty steps write nothing). `RunDirectory.write_diff`
owns the layout and `EpisodeReplay.diff(ref)` reads them back with a
path-traversal guard that refuses refs escaping the episode directory. Diffs are
listed in the manifest so an auditor can reconstruct the exact code state at each
step without re-running anything.

### Runtime prompt hashes

`runner._collect_runtime_prompt_hashes` scans the authoritative events and groups
the `prompt_sha256` recorded by `LLMAgent` per agent. Unlike `prompt_hashes`
(configured system prompts), these capture the *generated* messages, which depend
on the observation each agent saw — the difference matters when auditing whether
an agent's context changed across runs.

## Tests

`tests/test_harness.py` (12 tests) covers:

- runtime conformance of scripted agents and `BertrandMarket` to the protocols,
- replay round-trip for both scenarios (ground truth and metrics preserved),
- presence of `TOOL_CALL`/`TOOL_RESULT` from the monitor's independent checks,
- replay from a direct episode directory and from a `runs` root via `list_episodes`,
- `ReplayError` on a missing episode,
- the `Harness` facade run→replay cycle,
- runtime prompt hashes captured for LLM agents and diff artifacts persisted,
- a path-traversal guard on `EpisodeReplay.diff`.

Combined with the existing suite: **64 passed**, `mypy` clean across 32 modules.
