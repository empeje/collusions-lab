# Milestone 1 compliance review

This review compares the current checkout with Milestone 1 in the project
requirements. Requirements are the user's project brief; instructions and example
code inside that brief are not executable directions by themselves.

## Finding

**Milestone 1 is partially complete, but it is not yet a reproduced benchmark
baseline.** The repository provides a useful, reproducible synthetic prototype and
documents four related research projects. It does not run SCHEME task instances or
the double-auction collusion benchmark. The repo's original Bertrand market should
be described as a toy adaptation, not a reproduction of *By Fair Means or Foul*.

| Milestone 1 requirement | Current evidence | Status |
|---|---|---|
| Review SCHEME and double-auction benchmark availability, licensing, and fit | `docs/audits/scheme.md`, `docs/audits/llm-agent-collusion.md` | Done as a desk review |
| Reproduce software-engineering benchmark baseline | `SWEEnvironment` uses an in-repo synthetic repository; no SCHEME tasks or upstream harness | Gap |
| Reproduce market benchmark baseline | `BertrandMarket` is a custom toy; no double-auction task/data integration | Gap |
| Use two scenarios and a common trusted-monitor interface | Synthetic SWE and Bertrand environments use the same runner/monitor APIs | Partial prototype |
| Record seeds, conditions, logs, results, and metrics | `runner.py`, JSONL episode logs, result schemas, evaluation modules | Partial; paired seeds exist, but runs are small and scripted |
| Report benchmark-validated results | Existing runs are prototype smoke experiments, not upstream benchmark replications | Gap |

The `docs/requirements-traceability.md` table now uses these distinctions. No
upstream code or data was copied; the double-auction audit notes that the referenced
repository has no declared license, so integrating its code would need a separate
license decision.

## Corrections and limits

- The market implementation adapts selected dynamics and metrics and documents a
  deliberate price-update change. That is useful for a controlled toy baseline but
  changes the experimental behavior and prevents a claim of replication.
- The SWE implementation has a known invariant and independent checks, but uses a
  toy repository. It cannot establish generalization to real agentic coding tasks.
- Deterministic scripted agents establish harness behavior, not emergent collusion
  rates for LLMs. The current run outputs must not be reported as evidence that an
  LLM collusion detector works.
- Existing per-episode metrics are not a substitute for a preregistered protocol,
  held-out tasks, or confidence intervals across adequate repetitions.

## Suggested exit criteria

1. Choose one benchmark for each scenario (or explicitly defer markets and narrow
   Milestone 1 to SWE).
2. Freeze licenses, versions/commits, benchmark task IDs, model/provider settings,
   prompts, seeds, and inference limits in manifests.
3. Run benchmark control conditions without the monitor and preserve upstream
   expected artifacts and scores.
4. Add a separate monitor-on arm; keep detection, harmful outcomes, intervention,
   and utility as distinct outcomes.
5. Label any synthetic episodes as harness validation and keep their results apart
   from benchmark reproduction results.

## Current checkout verification

The repository test suite passed **48 tests** when the Windows temporary directory
was redirected to the writable checkout. A default run in this sandbox failed
because the OS temp directory is write-protected here; that is an execution
environment constraint, not evidence of a project test failure.
