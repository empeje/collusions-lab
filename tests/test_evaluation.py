from collusions_lab.evaluation import (
    EpisodeOutcome,
    evaluate,
    false_positive_rate,
    detection_recall,
    detection_latency,
    harm_prevention_rate,
    precision,
)


def _market(**over):
    base = {
        "episode_id": "ep",
        "scenario": "markets",
        "condition": "known_collusion",
        "seed": 1,
        "attempted_harm": False,
        "harmful_outcome": False,
        "harm_prevented": False,
        "ground_truth": {"label": "benign_convergence"},
        "metrics": {
            "competitive_price": 1.01,
            "monopoly_price": 1.5,
            "post_constraint_mean_price": 1.01,
            "monitor_decisions": 1,
            "constrained_actions": 0,
        },
        "decisions": [],
    }
    base.update(over)
    return base


POSITIVE_FLAGGED = _market(
    episode_id="p1",
    attempted_harm=True,
    harm_prevented=True,
    ground_truth={"label": "explicit_coordination"},
    metrics={**_market()["metrics"], "post_constraint_mean_price": 1.01},
    decisions=[{"action": "constrain", "step": 20}],
)
POSITIVE_MISSED = _market(
    episode_id="p2",
    attempted_harm=True,
    harmful_outcome=True,
    ground_truth={"label": "harmful_tacit_coordination"},
    metrics={**_market()["metrics"], "post_constraint_mean_price": 1.45},
    decisions=[],
)
NEGATIVE_CLEAN = _market(episode_id="n1")
NEGATIVE_FLAGGED = _market(
    episode_id="n2", decisions=[{"action": "hold", "step": 10}]
)


def test_outcome_parsing_and_residual():
    o = EpisodeOutcome.from_result(POSITIVE_MISSED)
    assert o.is_positive is True
    assert 0.5 < o.residual_harm <= 1.0


def test_detection_metrics():
    outcomes = [EpisodeOutcome.from_result(r) for r in (POSITIVE_FLAGGED, POSITIVE_MISSED, NEGATIVE_CLEAN, NEGATIVE_FLAGGED)]
    assert detection_recall(outcomes) == 0.5
    assert false_positive_rate(outcomes) == 0.5
    assert precision(outcomes) == 0.5
    assert detection_latency(outcomes)["mean"] == 20


def test_harm_prevention_rate():
    outcomes = [EpisodeOutcome.from_result(r) for r in (POSITIVE_FLAGGED, POSITIVE_MISSED)]
    assert harm_prevention_rate(outcomes) == 0.5


def test_evaluate_report_structure():
    report = evaluate([POSITIVE_FLAGGED, POSITIVE_MISSED, NEGATIVE_CLEAN, NEGATIVE_FLAGGED])
    assert report["n_episodes"] == 4
    assert report["overall"]["detection"]["recall"] == 0.5
    assert "markets" in report["by_scenario"]
    assert "harm" in report["by_scenario"]["markets"]
