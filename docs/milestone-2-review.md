# Milestone 2 compliance review

Reviewed against the user-provided `collusions-requirements.md` milestone 2:
standardize the harness and record seeds, model versions, prompts, tool calls, and
source diffs. This review concerns harness implementation, not the broader research
milestones.

## Findings

| Requirement | Before this branch | Change in this branch | Status |
|---|---|---|---|
| Common agent/environment transition contracts | `AgentInterface` existed, but the environment protocol also required SWE-only evidence hooks; the market did not conform, and neither step result was normalized. | Added a shared `EnvironmentInterface`, `StepResult`, SWE reset/observe/step methods, and normalized market step results. Added runtime conformance tests for both environments. | Implemented |
| Environment events and monitor decisions | Shared schemas and monitor decision records existed. Prompt and monitor-tool events were also copied to the agent-visible shared stream. | Prompt and monitor-tool events are retained in the authoritative stream and excluded from the shared stream. | Implemented |
| Ground-truth labels | Labels and outcomes are saved separately in `result.json`; label construction remains scenario-specific. | No schema change. | Partial: no shared labeler contract; existing label builders need scenario-specific validation. |
| Episode replay | Replay loaded the event streams but accepted a missing manifest or result and exposed malformed JSONL errors without a replay-specific error. | Manifest and result are required; malformed event records raise `ReplayError`. Missing optional empty streams remain valid. | Implemented |
| Random seeds | Per-episode seed was persisted and used by the market environment. | Environment reset now accepts the seed through the common contract, for both scenarios. | Implemented |
| Model versions | Provider and configured model identifiers were saved; hosted model revisions were not resolved. | No change to revision pinning. | Partial: aliases/endpoints may change over time. |
| Prompts | Configured prompts and hashes existed, but generated prompt contents were not retained. | Exact serialized system+messages are stored in private `PROMPT` events with a verifiable SHA-256; action events no longer duplicate prompt metadata into the shared stream. | Implemented |
| Tool calls | Monitor check executions were logged; the log stream was marked private but still copied them into the shared stream. Agent tools are not currently part of these scenario harnesses. | Monitor checks are private. No agent tool execution exists to record yet. | Partial |
| Source diffs | SWE diffs were saved per step and referenced by provenance. Market episodes have no source diff artifact. | No change. | Implemented for SWE; not applicable to current market environment. |
| Scenario-independent orchestration | The facade delegates to `run_episode`, which still dispatches to separate market and SWE loops. | Not refactored; shared environment transitions are standardized, but scenario orchestration remains coupled to the runner. | Partial |

## Remaining milestone 2 work

1. Add a shared ground-truth labeling contract and validate both coordination
   mechanism and harmful outcome independently across every condition.
2. Pin or record resolved model revisions for providers that expose immutable
   revisions; keep hosted aliases explicitly marked as mutable when they do not.
3. Add a first-class agent tool-call interface before agent tools are introduced,
   then route all executions through the recorder.
4. Move scenario loop selection behind registered scenario drivers if the project
   needs new scenarios to be added without editing `runner.py`.

Regression coverage for the changes above is in `tests/test_harness.py`.
