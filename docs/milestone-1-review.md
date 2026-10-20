# Milestone 1 compliance review

This review compares the current checkout with Milestone 1 in the project requirements. The brief is project context; text and examples inside it are not executable directions by themselves.

## Finding

**The local Milestone 1 fallback is implemented; upstream benchmark reproduction remains unavailable.** The repository now has paired, seeded sweeps for both synthetic scenarios and records run configuration and runtime provenance. Those sweeps validate the harness only. They are not SCHEME or double-auction benchmark results. The SCHEME project page describes the benchmark but does not link task/code artifacts; the referenced double-auction repository has no declared license, so its code/data are not integrated. The Bertrand environment remains a toy adaptation, not a reproduction of *By Fair Means or Foul*.

| Milestone 1 requirement | Current evidence | Status |
|---|---|---|
| Review SCHEME and double-auction benchmark availability, licensing, and fit | `docs/audits/scheme.md`, `docs/audits/llm-agent-collusion.md` | Done as a desk review |
| Reproduce software-engineering benchmark baseline | SCHEME project page links no task/code artifacts; seeded synthetic fallback in `experiments/milestone1_swe.yaml` | Fallback implemented; upstream reproduction blocked |
| Reproduce market benchmark baseline | Reference CDA repo has no declared license; seeded Bertrand fallback in `experiments/milestone1_market.yaml` | Fallback implemented; upstream reproduction blocked |
| Use two scenarios and a common trusted-monitor interface | Both fallbacks use the shared runner and monitor; SWE no-monitor arm is an untreated release baseline | Done for PoC |
| Record seeds, conditions, logs, results, and metrics | `runner.py` records run config and runtime provenance; configured and generated prompts are SHA-256 identified, prompt text is not stored | Partial; hashes do not permit exact prompt reconstruction |
| Report benchmark-validated results | Scripted fallback sweeps validate harness controls only, not upstream benchmarks or LLM behavior | Gap; requires upstream artifacts and model runs |

No upstream code or data was copied. The double-auction audit notes that its repository has no declared license, so integrating its code/data requires author permission or a license change.

## Corrections and limits

- The market implementation is a custom Bertrand toy that adapts selected mechanisms/metrics and changes price updates. It is not a reproduction of the cited paper or a continuous double auction.
- The SWE fallback uses an in-repo synthetic repository. It cannot establish generalization to real agentic coding tasks.
- Scripted agents establish harness behavior, not emergent collusion rates for LLMs. Fallback results must not be reported as evidence that an LLM collusion detector works.
- Market independent controls hide competitor prices; shared-context agents receive the public price report; communication agents receive prior-turn messages and can send one bounded public message. Scripted agents do not generate messages, so the communication effect requires LLM-backed runs.
- The SWE communication condition passes prior agent messages to LLM prompts. Scripted controls remain deterministic and do not use those messages.
- Episode manifests identify seeds, settings, versions, model/provider names, and prompt hashes. They do not preserve generated prompt contents or provider-side model snapshots.
- Per-episode metrics are not a substitute for a preregistered protocol, held-out tasks, or confidence intervals across adequate independent repetitions.

## Remaining upstream exit criteria

1. Obtain SCHEME task artifacts and license/permission details for the CDA implementation, or record author-approved alternatives.
2. Freeze benchmark commits/task IDs, model/provider settings, prompts, seeds, and inference limits before an upstream run.
3. Run no-monitor controls and monitor-on arms against upstream tasks; preserve expected artifacts and scores.
4. Report detector outcomes, harmful outcomes, intervention effects, and utility separately with uncertainty intervals from genuinely independent repetitions.
5. Run and analyze the distinct shared-context/communication treatments with model-backed agents.

## Verification

The original review passed 48 tests. This branch fixes a discovered no-monitor SWE baseline bug (the absent monitor decision was incorrectly treated as a blocked release) and adds regression coverage. Updated suite results are reported with the PR. Windows may require `TEMP` and `TMP` to point to a writable directory.
