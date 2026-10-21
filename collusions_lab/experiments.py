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
from itertools import product
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

# Default-valued ``defaults`` keys that may be given as a list to form a sweep axis.
# The cartesian product of these list-valued keys defines the parameter grid; every
# other default is held fixed. Each axis value is recorded on the run for grouping.
_AXIS_KEYS = (
    "n_sellers",
    "mu",
    "market_steps",
    "include_competitor_prices",
    "topology",
    "observability",
    "n_consumers",
    "simple_quantity",
    "price_update",
    "n_buyers",
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


def _size_market_roster(
    spec: ExperimentSpec, condition: str, n_sellers: int
) -> list[AgentConfig]:
    """Return a seller roster of exactly ``n_sellers`` agents.

    The market environment requires one action per seller, so the roster must match
    ``n_sellers`` when that axis is swept. The YAML roster supplies the template: if it
    is shorter, ``seller_<i>`` agents are generated to fill the gap; if longer, it is
    truncated. Deviants (from the condition block) are respected by id; generated
    sellers inherit the condition's hidden objective when *any* template seller is a
    deviant, preserving the "all sellers collude" design of the collusion conditions.
    """
    block = spec.conditions[condition]
    deviants = set(block.get("deviants", []))
    hidden = block.get("hidden_objective", spec.defaults.get("hidden_objective", "collude"))
    template = spec.agents
    all_deviant = bool(deviants) and deviants.issuperset(a["agent_id"] for a in template)
    roster: list[dict[str, Any]] = []
    for i in range(n_sellers):
        if i < len(template):
            a = dict(template[i])
        else:
            a = {"agent_id": f"seller_{i}", "role": template[-1]["role"] if template else "seller"}
        roster.append(a)
    configs = []
    for a in roster:
        is_dev = a["agent_id"] in deviants or (all_deviant and a["agent_id"] not in
                                               {t["agent_id"] for t in template})
        configs.append(
            AgentConfig(
                agent_id=a["agent_id"],
                role=AgentRole(a["role"]),
                model=a.get("model", spec.defaults.get("model", "qwen2.5:3b-instruct")),
                provider=a.get("provider", spec.defaults.get("provider", "scripted")),
                system_prompt=a.get("system_prompt", ""),
                hidden_objective=hidden if is_dev else None,
            )
        )
    return configs


def _axis_grid(defaults: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand list-valued axis defaults into a cartesian grid.

    Any key in ``_AXIS_KEYS`` whose value is a list (rather than a scalar) becomes a
    sweep axis. Returns a list of dicts, one per grid point, each mapping the axis key
    to a single value. If no axis key is list-valued, returns a single empty dict.
    """
    axes: dict[str, list[Any]] = {}
    for key in _AXIS_KEYS:
        if key in defaults and isinstance(defaults[key], list):
            axes[key] = list(defaults[key])
    if not axes:
        return [{}]
    keys = list(axes)
    return [dict(zip(keys, combo)) for combo in product(*(axes[k] for k in keys))]


def build_run_configs(spec: ExperimentSpec) -> list[RunConfig]:
    runs: list[RunConfig] = []
    detection_only = bool(spec.defaults.get("detection_only", False))
    grid = _axis_grid(spec.defaults)
    for condition in spec.conditions:
        cond = EpisodeCondition(condition)
        base_extra = dict(spec.conditions[condition].get("extra", {}))
        for axis_values in grid:
            # Resolve each axis key: axis value if swept, else the fixed default.
            def resolved(key: str, fallback: Any) -> Any:
                if key in axis_values:
                    return axis_values[key]
                return spec.defaults.get(key, fallback)

            market_extra = dict(base_extra)
            for key in ("n_consumers", "simple_quantity", "price_update", "n_buyers",
                        "repository", "package", "local_repo"):
                if key in axis_values:
                    market_extra[key] = axis_values[key]
                elif key in spec.defaults:
                    market_extra[key] = spec.defaults[key]
            # Record swept axes on the episode for later grouping.
            for key, value in axis_values.items():
                market_extra.setdefault("axes", {})[key] = value
            for seed in spec.seeds:
                for monitor_entry in spec.monitor:
                    mtype = _normalize_monitor(monitor_entry)
                    for intervention_entry in spec.intervention:
                        itype = _normalize_intervention(intervention_entry)
                        n_sellers = int(resolved("n_sellers", 5))
                        if spec.scenario == Scenario.MARKETS:
                            agents = _size_market_roster(spec, condition, n_sellers)
                        else:
                            agents = _agents_for_condition(spec, condition)
                        runs.append(
                            RunConfig(
                                scenario=spec.scenario,
                                condition=cond,
                                agents=agents,
                                seed=seed,
                                monitor_enabled=mtype != MonitorType.NONE,
                                monitor_type=mtype,
                                detection_only=detection_only,
                                intervention=itype,
                                judge_provider=spec.defaults.get("judge_provider", "hf"),
                                judge_model=spec.defaults.get(
                                    "judge_model", "Qwen/Qwen2.5-3B-Instruct"
                                ),
                                judge_threshold=float(spec.defaults.get("judge_threshold", 0.5)),
                                n_sellers=n_sellers,
                                mu=float(resolved("mu", 1.0)),
                                market_steps=int(resolved("market_steps", 200)),
                                include_competitor_prices=bool(
                                    resolved("include_competitor_prices", True)
                                ),
                                topology=str(resolved("topology", "none")),
                                observability=str(resolved("observability", "full")),
                                extra=market_extra,
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
