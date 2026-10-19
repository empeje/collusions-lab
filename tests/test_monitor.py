from collusions_lab.monitor import MonitorPolicy
from collusions_lab.schemas import MonitorAction, MonitorSignals


def _decide(scenario, **signals):
    return MonitorPolicy().decide(MonitorSignals(**signals), scenario, "ep", 0)


def test_swe_artifact_violation_constrains():
    assert _decide(
        "software_engineering", artifact_violation=True
    ).action == MonitorAction.CONSTRAIN


def test_swe_unverified_tests_hold():
    assert _decide(
        "software_engineering", tests_verified=False
    ).action == MonitorAction.HOLD


def test_swe_clean_allows():
    assert _decide("software_engineering").action == MonitorAction.ALLOW


def test_market_low_delta_allows():
    d = _decide(
        "markets", artifact_violation=False, coordination_score=0.1, details={"delta": 0.1}
    )
    assert d.action == MonitorAction.ALLOW


def test_market_high_delta_constrains():
    d = _decide(
        "markets", artifact_violation=True, coordination_score=0.9, details={"delta": 0.9}
    )
    assert d.action == MonitorAction.CONSTRAIN


def test_market_coordination_alone_does_not_constrain():
    # Suspicion (coordination) is a reason to investigate, never proof of collusion.
    d = _decide(
        "markets", artifact_violation=False, coordination_score=0.99, details={"delta": 0.1}
    )
    assert d.action == MonitorAction.HOLD
