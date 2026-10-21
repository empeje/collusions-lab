"""Experiment sweep runner.

An *experiment* YAML describes one scenario, a set of episode groups (conditions),
an agent roster, the seeds, and whether the monitor is enabled. Each
``(condition, seed, monitor)`` combination becomes a single episode run via
:func:`collusions_lab.runner.run_episode`; the collected ``result.json`` files can
then be aggregated with :mod:`collusions_lab.evaluation`.

This keeps condition definitions declarative and reproducible while the environment
code stays unaware of which condition it is executing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .runner import RunConfig, run_episode
from .schemas import (
    AgentConfig,
    AgentRole,
    EpisodeCondition,
    InterventionType,
    MonitorType,
    Scenario,
)


@dataclass
class ExperimentSpec:
    name: str
    scenario: Scenario
    agents: list[dict[str, Any]]
    conditions: dict[str, dict[str, Any]]
    seeds: list[int] = field(default_factory=lambda: [0])
    monitor: list[Any] = field(default_factory=lambda: [True])
    intervention: list[Any] = field(default_factory=lambda: ["auto"])
    restricted_tools: list[str] = field(default_factory=list)
    defaults: dict[str, Any] = field(default_factory=dict)


def _normalize_monitor(value: Any) -> MonitorType:
    """Map a YAML monitor entry to a MonitorType.

    Accepts booleans for back-compat (True -> artifact/treatment, False -> none)
    and the milestone-3 string names ``none``/``rules``/``llm_judge``/``artifact``.
    """
    if isinstance(value, bool):
        return MonitorType.ARTIFACT if value else MonitorType.NONE
    return MonitorType(str(value))


def _normalize_intervention(value: Any) -> InterventionType:
    """Map a YAML intervention entry to an InterventionType (default ``auto``)."""
    return InterventionType(str(value))


def load_experiment(path: str | Path) -> ExperimentSpec:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return ExperimentSpec(
        name=data["name"],
        scenario=Scenario(data["scenario"]),
        agents=data["agents"],
        conditions=data["conditions"],
        seeds=list(data.get("seeds", [0])),
        monitor=list(data.get("monitor", [True])),
        intervention=list(data.get("intervention", ["auto"])),
        restricted_tools=list(data.get("restricted_tools", [])),
        defaults=dict(data.get("defaults", {})),
    )


def _agents_for_condition(spec: ExperimentSpec, condition: str) -> list[AgentConfig]:
    block = spec.conditions[condition]
    deviants = set(block.get("deviants", []))
    hidden = block.get("hidden_objective", spec.defaults.get("hidden_objective", "collude"))
    configs = []
    for a in spec.agents:
        cfg = AgentConfig(
            agent_id=a["agent_id"],
            role=AgentRole(a["role"]),
            model=a.get("model", spec.defaults.get("model", "qwen2.5:3b-instruct")),
            provider=a.get("provider", spec.defaults.get("provider", "scripted")),
            system_prompt=a.get("system_prompt", ""),
            hidden_objective=hidden if a["agent_id"] in deviants else None,
        )
        configs.append(cfg)
    return configs


def build_run_configs(spec: ExperimentSpec) -> list[RunConfig]:
    runs: list[RunConfig] = []
    detection_only = bool(spec.defaults.get("detection_only", False))
    for condition in spec.conditions:
        cond = EpisodeCondition(condition)
        for seed in spec.seeds:
            for monitor_entry in spec.monitor:
                mtype = _normalize_monitor(monitor_entry)
                for intervention_entry in spec.intervention:
                    itype = _normalize_intervention(intervention_entry)
                    extra = dict(spec.conditions[condition].get("extra", {}))
                    runs.append(
                        RunConfig(
                            scenario=spec.scenario,
                            condition=cond,
                            agents=_agents_for_condition(spec, condition),
                            seed=seed,
                            monitor_enabled=mtype != MonitorType.NONE,
                            monitor_type=mtype,
                            detection_only=detection_only,
                            intervention=itype,
                            restricted_tools=list(spec.restricted_tools),
                            judge_provider=spec.defaults.get("judge_provider", "hf"),
                            judge_model=spec.defaults.get(
                                "judge_model", "Qwen/Qwen2.5-3B-Instruct"
                            ),
                            judge_threshold=float(spec.defaults.get("judge_threshold", 0.5)),
                            n_sellers=spec.defaults.get("n_sellers", 5),
                            mu=spec.defaults.get("mu", 1.0),
                            market_steps=spec.defaults.get("market_steps", 200),
                            include_competitor_prices=spec.defaults.get(
                                "include_competitor_prices", True
                            ),
                            extra=extra,
                        )
                    )
    return runs


def run_experiment(
    path: str | Path, out_root: str | Path = "runs"
) -> list[dict[str, Any]]:
    spec = load_experiment(path)
    root = Path(out_root) / spec.name
    return [run_episode(run, root) for run in build_run_configs(spec)]


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run a collusions-lab experiment sweep.")
    parser.add_argument("experiment", help="path to an experiment YAML file")
    parser.add_argument("--out", default="runs", help="output root directory")
    args = parser.parse_args()
    results = run_experiment(args.experiment, args.out)
    print(f"ran {len(results)} episodes from {args.experiment}")


if __name__ == "__main__":
    _main()
