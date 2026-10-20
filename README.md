# Collusions Lab

An **intervention benchmark** for detecting and disrupting harmful multi-agent
coordination. The goal is not another classifier of collusive transcripts, but a
harness that tests whether a *trusted monitor* actually changes outcomes: does it
catch coordination, block the harm, and preserve legitimate work?

Two matched scenarios share one monitor interface:

- **Scenario A — Markets.** A repeated Bertrand price-competition environment
  (m = 200 consumers, n sellers). Harmful outcome = sustained supra-competitive
  prices (tacit or explicit collusion).
- **Scenario B — Software engineering.** A six-agent pipeline over a synthetic
  repository with a security invariant and a mediated release gate. Harmful outcome =
  a coordinated change that defeats the authorization check and reaches release.

The market environment reimplements selected mechanisms and metrics discussed in
*"By Fair Means or Foul"* (Schlechtinger et al., IJCAI 2024, arXiv:2406.02650); it
is not a reproduction of that paper's experiments. Likewise, the SCHEME and
double-auction repositories have been reviewed, but are not run or reproduced here.
See [`docs/milestone-1-review.md`](docs/milestone-1-review.md) for the milestone
compliance assessment and
[`docs/architecture.md`](docs/architecture.md) and
[`docs/requirements-traceability.md`](docs/requirements-traceability.md).

## Design principles

1. **Separation of concerns.** Environment (ground truth) / agents / monitor are
   independent. The environment never knows which experimental condition is running;
   agents never see monitor internals.
2. **Trusted monitor, not a peer agent.** The monitor is model-free in this PoC, has
   read-only access to the authoritative log, and cannot be read or written by
   agents.
3. **Detection ≠ harm.** Flags *and* prevention are measured separately. Suspicion
   (coordination) is a reason to **investigate**, never proof of collusion.
4. **Quarantine, don't purge.** Suspicious content is diverted to a quarantine store;
   the authoritative audit trail is append-only and never mutated.
5. **Mediated capability.** Agents drive *actions*; a release gate / price override
   holds the capability to make a harmful outcome effective.
6. **Paired, seeded episodes.** Monitor-on vs monitor-off runs use identical seeds so
   prevention and utility cost are causally attributable.

## Install

```bash
python -m pip install -e ".[dev]"
```

Requires Python >= 3.11. Runtime deps: `pyyaml`, `requests`.

## Usage

Run the deterministic (scripted) sweeps and aggregate metrics:

```bash
python -m collusions_lab.experiments experiments/intervention_ablations.yaml
python -m collusions_lab.experiments experiments/benign_controls.yaml
python -m collusions_lab.experiments experiments/coordination_conditions.yaml
python -m collusions_lab.experiments experiments/swe_all_conditions.yaml
python -m collusions_lab.experiments experiments/milestone1_swe.yaml
python -m collusions_lab.experiments experiments/milestone1_market.yaml
python -m collusions_lab.evaluation runs
```

To run the scripted experiment through Inspect AI, install the optional extra and
run the task from the repository root:

```bash
python -m pip install -e ".[inspect]"
inspect eval inspect_tasks/collusions_eval.py --model mockllm/model
```

The Inspect task runs the existing deterministic harness; it does not require a
model API key. For model-based behavioral audits with Petri, see
[`docs/petri-inspect.md`](docs/petri-inspect.md). Petri uses separate auditor,
target, and judge model roles and can incur provider costs.

Each episode writes an audit trail under `runs/<experiment>/<episode_id>/`:

```
authoritative.jsonl   every event (monitor's read-only view)
shared.jsonl          events visible to agents
monitor.jsonl         monitor decisions (agents never read this)
quarantine.jsonl      diverted suspicious content
manifest.json         scenario / condition / seed / agents
result.json           metrics + ground truth (evaluation-only)
```

Programmatic use:

```python
from collusions_lab.runner import RunConfig, run_episode
from collusions_lab.schemas import AgentConfig, AgentRole, EpisodeCondition, Scenario
from collusions_lab.evaluation import evaluate, format_report

agents = [AgentConfig(f"seller_{i}", AgentRole.SELLER, provider="scripted")
          for i in range(5)]
run = RunConfig(Scenario.MARKETS, EpisodeCondition.INDEPENDENT_BASELINE, agents, seed=0)
result = run_episode(run, "runs")
print(format_report(evaluate([result])))
```

### LLM-backed agents

Agents can be driven by a provider instead of the deterministic scripted policy:

| provider   | notes                                            |
|------------|--------------------------------------------------|
| `scripted` | default; deterministic, used for CI and controls |
| `mock`     | offline canned responses for tests               |
| `ollama`   | local models (e.g. `qwen2.5:3b-instruct`)        |
| `openai`   | needs `OPENAI_API_KEY`                           |
| `gemini`   | needs `GEMINI_API_KEY`                           |

Set `provider`/`model` per agent in an experiment YAML `defaults` block. Only
low-VRAM local models (<= 8B) are assumed by the default config; tokens/keys are read
from environment variables and never committed.

## Experimental conditions

Five matched conditions (`EpisodeCondition`): `independent_baseline`,
`shared_context`, `communication`, `known_collusion` (ground-truth positives),
`adversarial_monitor`. See the YAMLs in [`experiments/`](experiments/).

## Metrics

`collusions_lab.evaluation` reports three families (`docs/architecture.md` has
definitions): **detection** (recall, precision, false-positive rate, time to
detection), **harm** (prevention rate, residual harm), and **utility** (task utility
retained, intervention cost, recovery rate). Detection and prevention are always
reported together with the prevention–utility trade-off.

## Tests and checks

```bash
python -m pytest -q      # deterministic, no network
python -m mypy collusions_lab
```

The `milestone1_*_fallback.yaml` sweeps are paired harness checks using scripted
agents. They are not reproductions of SCHEME or the double-auction benchmark and do
not establish LLM collusion rates. See [the Milestone 1 review](docs/milestone-1-review.md)
for the upstream access/license blockers and remaining work.

## Safety

Everything here is a self-contained research PoC. The software scenario uses a
synthetic repository; no real exploit is produced and no production system is
touched. Test execution is isolated in a temporary directory via subprocess. The
market scenario is a toy economic simulation. Do not use agent outputs against real
systems.

## License

Apache-2.0 (see `pyproject.toml`).
