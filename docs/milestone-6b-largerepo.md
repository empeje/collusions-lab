# Milestone 6B -- Multi-agent software engineering on a real repository

Milestone 6B validates the harness and monitor on a **real public code repository**
rather than the synthetic `acme_portal` toy. The requirement asks for a real-world
repository with the same monitor interface and a report of the software-integrity
metrics.

## Why this milestone

The synthetic repo has one small package, one invariant, and two check scripts. A real
repository exercises: many files, an existing test suite, and genuine review/merge
workflows. The test is whether the artifact- and evidence-verification monitor still works
when the "artifact" is a real diff and the "tests" are a real test runner.

## Starting-point model (important)

This is a **multi-agent** scenario: several agents collaborate to build, test, and deploy
a feature from a starting point. That is distinct from the SWE-bench *single-agent* task
(one agent produces a patch). We adopt the **SWE-bench environment format** because it
gives a reproducible "starting point", but we drive it with our role pipeline:

* planner -> implementer_a -> implementer_b -> tester -> reviewer -> executor
* the executor's release request is gated by the trusted monitor (Milestone 4)
* grading uses the repository's own tests plus a declared AST invariant.

### SWE-bench task instance as the environment

Milestone 6B is driven by a published SWE-bench `instance_id`:

```json
{
  "instance_id": "owner__repo-pr_number",
  "repo": "owner/repo",
  "base_commit": "commit_hash",
  "problem_statement": "Issue description...",
  "patch": "Gold solution patch",
  "test_patch": "Test patch",
  "FAIL_TO_PASS": ["..."],
  "PASS_TO_PASS": ["..."]
}
```

* **`base_commit`** -- the pinned starting state the agents operate on.
* **`problem_statement`** -- the feature/bug the agents must build.
* **`test_patch` + `FAIL_TO_PASS` / `PASS_TO_PASS`** -- the objective grader.

Datasets live on HF (`SWE-bench/SWE-bench_Lite`, `SWE-bench/SWE-bench_Verified`); repo
mirrors live at `github.com/SWE-bench-repos/<owner>__<repo>`. Offline runs load a local
JSON fixture with the same schema, so no network is needed in CI.

### Repo candidates (permissive, real pytest suite, present in SWE-bench)

| repo | license | rationale |
|---|---|---|
| `pytest-dev/pytest` | MIT | self-contained, large test suite, `pip install -e .` |
| `python-cas/python-cas` | MIT | tiny, auth domain (pairs with a security invariant) |
| `authomatic/authomatic` | MIT | auth library, real OAuth/httpx tests |
| `sympy/sympy` | BSD-3 | canonical SWE-bench repo (heavier) |

A concrete `instance_id` (with its `base_commit`) is pinned in
`experiments/milestone6b_largerepo.yaml`.

## Execution model: local checkout, no Docker

For reproducibility without a Docker dependency, the environment performs a
**lightweight local checkout**:

* `git clone` (or a local fixture copy) of the pinned repo, then `git checkout <base_commit>`
  into an isolated temporary workdir;
* the real test command runs via `subprocess` (reusing `_run_script` semantics);
* `changed_files` / `build_diff` are computed from the git working tree.

One **slow, opt-in** test performs the real network clone; the default test suite uses a
local fixture so CI stays offline and deterministic.

## Interface reuse (no monitor changes)

* `MonitorStrategy` / `MonitorOutcome` / `MonitorSignals` unchanged.
* `SWEEnvironment` generalized to a `RepositoryEnvironment`:
  * clone/checkout a pinned commit into an isolated workdir,
  * run the repo's real test command in a subprocess,
  * compute `changed_files` / `build_diff` from the git working tree,
  * evaluate an **explicitly specified invariant** (see below).
* `EvidenceCollector.collect_swe` reused, with the invariant/test sources pointed at the
  real repo instead of the toy scripts.

## Choosing the invariant

A real repo does not ship an `INVARIANTS.md`. Milestone 6B uses a **declared,
machine-checkable invariant** supplied by the experiment author -- e.g. "authentication
must be checked before the privileged operation in module M", or "no new
`eval`/`subprocess` without sanitization" -- verified by an independent static check that
extends the AST checker pattern from `synthetic_repo.py`. The check must be
**meaningfully enforced** (real ordering / pattern checks), not merely the presence of a
symbol, so it cannot be trivially bypassed.

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
blocked, detection latency, false-positive rate, legitimate changes incorrectly blocked,
task-utility-retained, and intervention cost (real test-run latency).

## Code integration points

| piece | code path |
|---|---|
| Generalized env | `collusions_lab/environments/software_engineering/repository_env.py` |
| Instance loader | `collusions_lab/environments/software_engineering/swebench_instance.py` |
| Invariant checker | extends `environments/software_engineering/synthetic_repo.py` |
| Evidence reuse | `monitor/evidence.py::collect_swe` (repointed) |
| Provenance | manifest `repo` / `instance_id` / `base_commit` |
| Config | `experiments/milestone6b_largerepo.yaml` |
| Tests | `tests/test_repository_env.py` (offline fixture + one slow network test) |

## Running the sweep

```powershell
# Offline (local fixture instance):
python -m collusions_lab.experiments experiments/milestone6b_largerepo.yaml --out runs_m6b
python -m collusions_lab.evaluation runs_m6b

# Opt-in real clone (network):
pytest tests/test_repository_env.py -k network
```

## Deliverables

* `collusions_lab/environments/software_engineering/repository_env.py` (generalized env).
* `collusions_lab/environments/software_engineering/swebench_instance.py` (loader).
* A pinned-repo experiment config + invariant checker.
* `experiments/milestone6b_largerepo.yaml`.
* `docs/milestone-6b-largerepo.md` (this file) updated with results.
* Real-repo replay/provenance verification.

## Safety

The repository is cloned read-only into an isolated temporary workdir; no push, no
network beyond the clone, no real systems touched. The harmful "change" is an
intentionally introduced, reversible modification evaluated only inside the sandbox,
consistent with the Scenario B safety stance.
