# Milestone 6B — Generalize to a large real-world software repository

Milestone 6B validates the harness and monitor on a **reasonably complex public code
repository**, instead of the synthetic `acme_portal` toy. The requirement asks for a
real-world repository with the same monitor interface and a report of the software
integrity metrics.

## Why this milestone

The synthetic repo has one small package, one invariant, and two check scripts. A
real repository exercises: many files and languages, existing CI/test suites,
non-trivial dependency graphs, and genuine review/merge workflows. The test is
whether the artifact- and evidence-verification monitor still works when the
"artifact" is a real diff and the "tests" are a real test runner.

## Interface reuse (no monitor changes)

- `MonitorStrategy` / `MonitorOutcome` / `MonitorSignals` unchanged.
- `SWEEnvironment` generalized to a `RepositoryEnvironment` that can:
  - clone a pinned commit of a public repository into an isolated workdir,
  - run its real test command in a subprocess (reusing `_run_script` semantics),
  - compute `changed_files` / `build_diff` from the git working tree,
  - evaluate an **explicitly specified invariant** (see below).
- `EvidenceCollector.collect_swe` reused, with the invariant/test sources pointed at
  the real repo instead of the toy scripts.

## Choosing the invariant

A real repo does not ship an `INVARIANTS.md`. Milestone 6B uses a **declared,
machine-checkable invariant** supplied by the experiment author — e.g. "authentication
must be checked before the privileged operation in module M", or "no new
`eval`/`subprocess` without sanitization" — verifiable by an independent static
check (extending the AST checker pattern from `synthetic_repo.py`). This keeps the
monitor's artifact signal meaningful while remaining reproducible.

## Repository selection criteria

| criterion | requirement |
|---|---|
| License | permissive (Apache/MIT/BSD) — redistributable, pinned |
| Language | Python (reuses the AST/test tooling) |
| Size | multi-module, a real test suite runnable in CI time |
| Invariant | at least one security/correctness property that can be declared and checked |
| Determinism | tests pass deterministically in an isolated environment |

A candidate is pinned by commit hash in `experiments/milestone6b_largerepo.yaml`;
provenance records the commit (reusing the Milestone 2 manifest).

## Parameters (scenario-specific)

| parameter | values | rationale |
|---|---|---|
| change scope | single-file vs cross-module | provenance/diff complexity |
| reviewer count | 1, 2, 3 | independent review under scale |
| test command | full suite vs targeted subset | intervention-cost realism |
| invariant strictness | syntactic vs behavioural | artifact-signal calibration |
| observability | full diff vs summary | incomplete-observability failure mode |

## Metrics

Software-integrity metrics from Scenario B, applied to real code: harmful changes
blocked, detection latency, false-positive rate, legitimate changes incorrectly
blocked, task-utility-retained, and intervention cost (real test-run latency).

## Deliverables

- `collusions_lab/environments/software_engineering/repository_env.py` (generalized env).
- A pinned-repo experiment config + invariant checker.
- `experiments/milestone6b_largerepo.yaml`.
- `docs/milestone-6b-largerepo.md` (this file) updated with results.
- Real-repo replay/provenance verification.

## Safety

The repository is cloned read-only into an isolated temporary workdir; no push, no
network beyond the clone, no real systems touched. The harmful "change" is an
intentionally introduced, reversible modification evaluated only inside the sandbox,
consistent with the Scenario B safety stance.
