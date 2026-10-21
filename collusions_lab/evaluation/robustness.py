"""Robustness analysis (Milestone 5): axis breakdowns and bootstrap intervals.

The robustness sweep varies one structural axis at a time (communication topology,
observability level, seller count, market depth) and measures whether each monitor's
detection and prevention hold up. Two tools support that analysis:

* :func:`by_axis` -- slice an episode set by an axis value and report the standard
  metric triple (detection / harm / utility) per slice.
* :func:`bootstrap_ci` -- a paired-style non-parametric confidence interval for any
  scalar metric over a set of episodes, so small sample sizes are not over-read.

The axes are read from :class:`~collusions_lab.evaluation.detection_metrics.EpisodeOutcome`;
valid axis names are the field names defined on that dataclass (``topology``,
``observability``, ``monitor_type``, ``intervention``, ``condition``, ``seed``,
``scenario``, ...). Any attribute present on the outcome objects can be used.
"""

from __future__ import annotations

import random
from typing import Any, Callable

from .detection_metrics import EpisodeOutcome, detection_recall, detection_summary
from .harm_metrics import harm_prevention_rate, harm_summary, residual_harm
from .utility_metrics import utility_summary

__all__ = ["by_axis", "bootstrap_ci", "axis_values", "robustness_intervals"]

# Axes that the Milestone 5 robustness sweep treats as first-class. Documented so the
# report and tests agree on naming; ``by_axis`` itself accepts any outcome attribute.
ROBUSTNESS_AXES = (
    "topology",
    "observability",
    "n_sellers",
    "mu",
    "market_steps",
    "monitor_type",
    "intervention",
)


def axis_values(outcomes: list[EpisodeOutcome], axis: str) -> list[Any]:
    """Return the sorted distinct values observed for ``axis``."""
    seen = {getattr(o, axis) for o in outcomes if hasattr(o, axis)}
    return sorted(seen, key=lambda v: (str(type(v)), v))


def by_axis(
    outcomes: list[EpisodeOutcome],
    axis: str,
    baseline: list[EpisodeOutcome] | None = None,
) -> dict[str, Any]:
    """Break metrics down by a single structural axis.

    Returns a mapping ``{str(value): {n_episodes, detection, harm, utility}}`` plus a
    top-level ``"axis"`` key naming the sliced attribute. ``baseline`` (paired
    no-monitor episodes) is used for task-utility-retained, matched by axis value.
    """
    baseline = baseline or []
    if not any(hasattr(o, axis) for o in outcomes):
        raise ValueError(f"unknown robustness axis: {axis!r}")
    out: dict[str, Any] = {"axis": axis}
    for value in axis_values(outcomes, axis):
        sub = [o for o in outcomes if getattr(o, axis, None) == value]
        sub_base = [o for o in baseline if getattr(o, axis, None) == value]
        out[str(value)] = {
            "n_episodes": len(sub),
            "detection": detection_summary(sub),
            "harm": harm_summary(sub),
            "utility": utility_summary(sub, sub_base or None),
        }
    return out


def bootstrap_ci(
    metric_fn: Callable[[list[EpisodeOutcome]], float],
    outcomes: list[EpisodeOutcome],
    n: int = 1000,
    alpha: float = 0.05,
    seed: int = 1234,
) -> dict[str, Any]:
    """Non-parametric bootstrap confidence interval for a scalar metric.

    Resamples ``outcomes`` with replacement ``n`` times, evaluates ``metric_fn`` on
    each resample, and returns the ``alpha/2`` and ``1 - alpha/2`` percentiles. The
    point estimate is ``metric_fn(outcomes)`` on the full set.

    ``seed`` makes the interval deterministic for tests and reports.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    if not outcomes:
        return {"point": metric_fn([]), "low": None, "high": None, "n": n, "alpha": alpha}
    point = float(metric_fn(outcomes))
    rng = random.Random(seed)
    size = len(outcomes)
    samples: list[float] = []
    for _ in range(n):
        resample = [outcomes[rng.randrange(size)] for _ in range(size)]
        samples.append(float(metric_fn(resample)))
    samples.sort()
    lo_idx = max(0, int((alpha / 2) * n) - 1) if alpha > 0 else 0
    hi_idx = min(n - 1, int((1 - alpha / 2) * n))
    low = samples[lo_idx]
    high = samples[hi_idx]
    return {
        "point": round(point, 4),
        "low": round(low, 4),
        "high": round(high, 4),
        "n": n,
        "alpha": alpha,
    }


def robustness_intervals(
    outcomes: list[EpisodeOutcome],
    axes: tuple[str, ...] = ROBUSTNESS_AXES,
    n: int = 1000,
    alpha: float = 0.05,
    seed: int = 1234,
) -> dict[str, Any]:
    """Bootstrap CIs for key metrics: overall and per varying axis value.

    Reports intervals for detection recall, harm-prevention rate, and residual harm,
    both pooled and sliced by every axis that actually varies. Small-sample intervals
    are the point: they keep per-cell numbers from being over-read.
    """
    def _triple(sub: list[EpisodeOutcome]) -> dict[str, Any]:
        return {
            "n": len(sub),
            "recall": bootstrap_ci(detection_recall, sub, n=n, alpha=alpha, seed=seed),
            "harm_prevention": bootstrap_ci(
                harm_prevention_rate, sub, n=n, alpha=alpha, seed=seed
            ),
            "residual_harm": bootstrap_ci(residual_harm, sub, n=n, alpha=alpha, seed=seed),
        }

    report: dict[str, Any] = {"overall": _triple(outcomes)}
    for axis in axes:
        if not any(hasattr(o, axis) for o in outcomes):
            continue
        values = axis_values(outcomes, axis)
        if len(values) <= 1:
            continue
        report[axis] = {
            str(value): _triple(
                [o for o in outcomes if getattr(o, axis, None) == value]
            )
            for value in values
        }
    return report
