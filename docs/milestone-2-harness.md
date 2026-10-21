# Milestone 2 — Standardised Harness

Milestone 1 produced a working, instrumented, two-scenario benchmark. Milestone 2
turns it into a **standard harness**: one explicit contract that scenarios,
agents, monitors, external tooling (Inspect/Petri), and the replay/audit path all
target, with no scenario-specific coupling in the orchestration layer.

## Goals

1. **Common contracts** — agents and environments expose standard action and
   transition shapes; scenario-specific experiment orchestration remains in the
   runner for now.
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
- `EnvironmentInterface` — common `reset`, `observe`, and `step` methods returning
  the normalized `StepResult`. Both `BertrandMarket` and `SWEEnvironment` satisfy it.
- `EvidenceInterface` — optional artifact evidence hooks (`changed_files`,
  `build_diff`) used by the SWE monitor path; these are not required of markets.
- `StepResult` — a normalized `(step, done, info)` record so scenario `step`
  return shapes converge.
- `Harness` — a thin facade over `runner.run_episode` that pins the entry point
  and pairs every run with its replay.

Scenario-specific monitoring still uses scenario evidence hooks. The common
environment contract standardizes episode reset, observation, and transitions; it
does not make the two scenario-specific monitor implementations interchangeable.

## Replay (`collusions_lab/harness/replay.py`)

`replay_episode(run, episode_id=None)` loads `manifest.json`, `result.json`, and
the four JSONL streams (authoritative, shared, monitor, quarantine) into an
immutable `EpisodeReplay`. Highlights:

- Read-only: replay never mutates the authoritative log.
- Integrity first: a missing manifest or result raises `ReplayError`; malformed JSON
  or event records raise rather than silently degrading.
- Typed accessors: `.provenance`, `.agents`, `.ground_truth`, `.decisions()`,
  `.agent_events()`.
- `list_episodes(runs_root)` enumerates every episode directory for batch audits.

## Event taxonomy

Milestone 1 emitted `ACTION`, `MESSAGE`, `CLAIM`, `DECISION`, `MONITOR`. Milestone
2 adds:

- `PROMPT` — recorded whenever an LLM agent returns `_llm` metadata, carrying the
  provider-reported model, the exact serialized system+messages, and a
  `prompt_sha256` over that prompt. Prompt events are authoritative/private and are
  not copied into the agent-visible shared stream.
- `TOOL_CALL` / `TOOL_RESULT` — recorded around the trusted monitor's independent
  test execution (`invariant_check`, `behavior_tests`). These are the monitor's
  own private actions, tagged `actor="monitor"`, and are excluded from the
  agent-visible shared stream.

## Provenance manifest

The episode manifest includes an episode ID and a
`provenance: ProvenanceRecord` that `runner._build_provenance` populates with:

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

### Runtime prompts and hashes

`runner._collect_runtime_prompt_hashes` scans the authoritative events and groups
the `prompt_sha256` recorded by `LLMAgent` per agent. The exact serialized prompt is
also stored on the private `PROMPT` event so the hash can be checked and the request
audited. Unlike `prompt_hashes`
(configured system prompts), these capture the *generated* messages, which depend
on the observation each agent saw — the difference matters when auditing whether
an agent's context changed across runs.

## Condition controls (shared context & communication)

Milestone 1's five conditions now drive real, distinct harness behaviour rather
than being protocol placeholders. The runner threads them through both scenarios:

- **Independent baseline** — market sellers no longer receive competitor prices
  (`include_competitors` is forced off for `INDEPENDENT_BASELINE`).
- **Shared context** — the public price report is included in the market
  observation, as before.
- **Communication** — the harness carries a per-round `team_messages` list:
  - *Market*: each seller's observation gets the previous round's messages; a
    seller may return an optional `message` JSON field (parsed by
    `parse_market_action`), which the runner strips, truncates to 500 chars, and
    emits as a `MESSAGE` event that all sellers see next round.
  - *SWE*: prior `MESSAGE` events are passed into the agent context as
    `team_messages`; `_build_swe_agents` renders the full observation (minus
    `team_messages`) as JSON and appends the prior messages to the prompt for the
    `COMMUNICATION` condition.

Scripted controls stay deterministic and do not generate messages, so the
communication treatment's effect requires LLM-backed runs (see
`docs/milestone-1-review.md`). `MESSAGE` events are part of the authoritative
trail and remain visible to the monitor's evidence collector.

## Related integration changes

This harness branch also carries Milestone 1 fixes cherry-picked alongside the
harness work:

- `ProvenanceRecord.prompts_hash` was renamed to `prompt_hashes`, so the manifest
  field name, `runner._build_provenance`, and `EpisodeReplay.provenance` all agree.
- `docs/petri-inspect.md` records the local Petri smoke-test limits, and
  `docs/milestone-1-review.md` / `docs/requirements-traceability.md` describe the
  now-distinct condition treatments.

## Tests

`tests/test_harness.py` covers:

- runtime conformance of scripted agents, `BertrandMarket`, and `SWEEnvironment` to
  the common protocols,
- replay round-trip for both scenarios (ground truth and metrics preserved),
- presence of private `TOOL_CALL`/`TOOL_RESULT` events from the monitor's independent
  checks, and prompt/tool exclusion from the shared agent stream,
- replay from a direct episode directory and from a `runs` root via `list_episodes`,
- `ReplayError` on missing episodes/artifacts and malformed event streams,
- the `Harness` facade run→replay cycle,
- runtime prompt hashes captured for LLM agents and diff artifacts persisted,
- a path-traversal guard on `EpisodeReplay.diff`.

Validation on the milestone 2 compliance branch: full suite **70 passed**;
`mypy` clean across 32 source files.
