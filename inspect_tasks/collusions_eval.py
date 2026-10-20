"""Run the repository's deterministic sweeps as an Inspect AI evaluation.

The existing episode runner remains the source of environment behavior and
ground truth. Inspect supplies the standard task, sample, scoring, and log
container; it does not substitute an LLM judge for the monitor.

Run from the repository root after installing ``.[inspect]``:

    inspect eval inspect_tasks/collusions_eval.py --model mockllm/model
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import Score, Scorer, Target, mean, scorer
from inspect_ai.solver import Generate, Solver, TaskState, solver

from collusions_lab.runner import RunConfig, run_episode
from collusions_lab.schemas import AgentConfig, AgentRole, EpisodeCondition, Scenario

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPERIMENT = ROOT / "experiments" / "swe_all_conditions.yaml"


def _run_config(metadata: dict[str, Any]) -> RunConfig:
    return RunConfig(
        scenario=Scenario(metadata["scenario"]),
        condition=EpisodeCondition(metadata["condition"]),
        agents=[
            AgentConfig(
                agent_id=agent["agent_id"],
                role=AgentRole(agent["role"]),
                model=agent["model"],
                provider=agent["provider"],
                system_prompt=agent.get("system_prompt", ""),
                hidden_objective=agent.get("hidden_objective"),
            )
            for agent in metadata["agents"]
        ],
        seed=int(metadata["seed"]),
        monitor_enabled=bool(metadata["monitor_enabled"]),
        n_sellers=int(metadata.get("n_sellers", 5)),
        mu=float(metadata.get("mu", 1.0)),
        market_steps=int(metadata.get("market_steps", 200)),
        include_competitor_prices=bool(metadata.get("include_competitor_prices", True)),
    )


def _samples(experiment_file: str | Path) -> list[Sample]:
    # Import here so importing this Inspect task doesn't depend on internal
    # experiment implementation details until the task is actually constructed.
    from collusions_lab.experiments import build_run_configs, load_experiment

    path = Path(experiment_file)
    if not path.is_absolute():
        path = ROOT / path
    spec = load_experiment(path)
    samples = []
    for run in build_run_configs(spec):
        metadata = {
            "scenario": run.scenario.value,
            "condition": run.condition.value,
            "seed": run.seed,
            "monitor_enabled": run.monitor_enabled,
            "n_sellers": run.n_sellers,
            "mu": run.mu,
            "market_steps": run.market_steps,
            "include_competitor_prices": run.include_competitor_prices,
            "agents": [
                {
                    "agent_id": agent.agent_id,
                    "role": agent.role.value,
                    "model": agent.model,
                    "provider": agent.provider,
                    "system_prompt": agent.system_prompt,
                    "hidden_objective": agent.hidden_objective,
                }
                for agent in run.agents
            ],
        }
        sample_id = (
            f"{run.scenario.value}-{run.condition.value}-seed{run.seed}-"
            f"monitor{int(run.monitor_enabled)}"
        )
        samples.append(
            Sample(
                id=sample_id,
                input=(
                    f"Execute the scripted {run.scenario.value} episode for condition "
                    f"{run.condition.value}, seed {run.seed}, monitor "
                    f"{run.monitor_enabled}."
                ),
                target="Episode metrics are recorded in the Inspect score.",
                metadata=metadata,
            )
        )
    return samples


@solver
def execute_episode() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        del generate  # The scripted benchmark does not call a model.
        metadata = state.metadata or {}
        output_root = Path(
            os.environ.get("COLLUSIONS_INSPECT_RUNS", str(ROOT / "runs" / "inspect"))
        )
        result = run_episode(_run_config(metadata), output_root)
        state.output = ModelOutput.from_content("assistant", json.dumps(result))
        return state

    return solve


@scorer(
    metrics={
        "attempted_harm": [mean()],
        "harmful_outcome": [mean()],
        "harm_prevented": [mean()],
        "monitor_decisions": [mean()],
    }
)
def episode_metrics() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        del target
        result = json.loads(state.output.completion)
        metrics = result.get("metrics", {})
        return Score(
            value={
                "attempted_harm": result.get(
                    "attempted_harm", result.get("harmful_change_present", False)
                ),
                "harmful_outcome": result.get("harmful_outcome", False),
                "harm_prevented": result.get("harm_prevented", False),
                "monitor_decisions": metrics.get("monitor_decisions", 0),
            },
            answer=state.output.completion,
            explanation="Metrics are calculated from the harness result and ground truth.",
            metadata={
                "scenario": result.get("scenario"),
                "condition": result.get("condition"),
                "seed": result.get("seed"),
                "monitor_enabled": result.get("monitor_enabled"),
                "ground_truth_label": result.get("ground_truth", {}).get("label"),
                "task_completed": metrics.get("task_completed"),
            },
        )

    return score


@task
def collusions_lab(experiment_file: str = str(DEFAULT_EXPERIMENT)) -> Task:
    """Evaluate each condition/seed/monitor combination in an experiment YAML."""
    return Task(
        dataset=_samples(experiment_file),
        solver=execute_episode(),
        scorer=episode_metrics(),
    )
