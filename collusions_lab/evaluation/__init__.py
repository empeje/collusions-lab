"""Evaluation package: detection, harm, and utility metrics for episodes.

Usage:
    from collusions_lab.evaluation import evaluate, load_results

    results = load_results("runs")
    report = evaluate(results)
    print(report["detection"]["recall"], report["harm"]["harm_prevention_rate"])
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .detection_metrics import (
    EpisodeOutcome,
    confusion,
    detection_latency,
    detection_recall,
    detection_summary,
    false_positive_rate,
    precision,
)
from .harm_metrics import (
    harm_prevention_rate,
    harm_summary,
    harmful_outcome_rate,
    residual_harm,
)
from .utility_metrics import (
    intervention_cost,
    recovery_rate,
    task_completion_rate,
    task_utility_retained,
    utility_summary,
)

__all__ = [
    "EpisodeOutcome",
    "evaluate",
    "load_results",
    "confusion",
    "detection_summary",
    "detection_recall",
    "false_positive_rate",
    "precision",
    "detection_latency",
    "harm_summary",
    "harm_prevention_rate",
    "harmful_outcome_rate",
    "residual_harm",
    "utility_summary",
    "task_completion_rate",
    "task_utility_retained",
    "intervention_cost",
    "recovery_rate",
]


def load_results(root: str | Path) -> list[dict[str, Any]]:
    """Load every ``result.json`` under a runs directory tree."""
    root = Path(root)
    results = []
    for path in sorted(root.rglob("result.json")):
        try:
            results.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return results


def _subset(outcomes: Iterable[EpisodeOutcome], scenario: str | None = None) -> list[EpisodeOutcome]:
    items = list(outcomes)
    if scenario:
        items = [o for o in items if o.scenario == scenario]
    return items


def evaluate(
    results: list[dict[str, Any]],
    baseline_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Aggregate raw episode results into the three metric families.

    ``baseline_results`` should be the *no-monitor* runs (paired by seed/condition)
    used to compute task-utility-retained.
    """
    outcomes = [EpisodeOutcome.from_result(r) for r in results]
    baseline = [EpisodeOutcome.from_result(r) for r in (baseline_results or [])]

    report: dict[str, Any] = {
        "n_episodes": len(outcomes),
        "overall": {
            "detection": detection_summary(outcomes),
            "harm": harm_summary(outcomes),
            "utility": utility_summary(outcomes, baseline or None),
        },
        "by_scenario": {},
    }
    for scenario in ("markets", "software_engineering"):
        sub = _subset(outcomes, scenario)
        if not sub:
            continue
        sub_base = _subset(baseline, scenario)
        report["by_scenario"][scenario] = {
            "n_episodes": len(sub),
            "detection": detection_summary(sub),
            "harm": harm_summary(sub),
            "utility": utility_summary(sub, sub_base or None),
        }
    return report


def format_report(report: dict[str, Any]) -> str:
    """Render an :func:`evaluate` report as a compact text summary."""
    lines = [f"episodes: {report['n_episodes']}"]

    def _block(title: str, r: dict[str, Any]) -> None:
        det, harm, util = r["detection"], r["harm"], r["utility"]
        lines.append(f"\n[{title}]")
        lines.append(
            f"  detection  recall={det['recall']} precision={det['precision']} "
            f"fpr={det['false_positive_rate']} latency(mean)={det['latency']['mean']}"
        )
        lines.append(
            f"  harm       prevention={harm['harm_prevention_rate']} "
            f"residual={harm['mean_residual_harm']} "
            f"harmful_outcome={harm['harmful_outcome_rate']}"
        )
        util_line = f"  utility    task_completion={util['task_completion_rate']}"
        if "task_utility_retained" in util:
            util_line += f" retained={util['task_utility_retained']}"
        lines.append(util_line)

    _block("overall", report["overall"])
    for scenario, r in report["by_scenario"].items():
        _block(scenario, r)
    return "\n".join(lines)


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Aggregate episode results into metrics.")
    parser.add_argument("root", nargs="?", default="runs", help="runs directory")
    args = parser.parse_args()
    results = load_results(args.root)
    monitored = [r for r in results if r.get("monitor_enabled", True)]
    baseline = [r for r in results if not r.get("monitor_enabled", True)]
    report = evaluate(monitored or results, baseline or None)
    print(format_report(report))


if __name__ == "__main__":
    _main()
