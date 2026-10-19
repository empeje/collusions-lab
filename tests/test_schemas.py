from collusions_lab.schemas import (
    AgentConfig,
    AgentRole,
    EpisodeCondition,
    Event,
    EventType,
    GroundTruth,
    GroundTruthLabel,
    MonitorSignals,
    jsonable,
)


def test_enum_values_are_stable():
    assert EpisodeCondition.INDEPENDENT_BASELINE.value == "independent_baseline"
    assert EpisodeCondition.KNOWN_COLLUSION.value == "known_collusion"
    assert len(list(EpisodeCondition)) == 5


def test_jsonable_converts_enums_and_dataclasses():
    gt = GroundTruth(label=GroundTruthLabel.EXPLICIT_COORDINATION, harmful_outcome=True)
    data = jsonable(gt)
    assert data["label"] == "explicit_coordination"
    assert data["harmful_outcome"] is True


def test_event_serialisation_roundtrip():
    ev = Event(
        episode_id="ep_1",
        step=3,
        agent_id="seller_0",
        role=AgentRole.SELLER,
        type=EventType.ACTION,
        content={"action": 2},
    )
    data = jsonable(ev)
    assert data["role"] == "seller"
    assert data["type"] == "action"
    assert data["content"] == {"action": 2}


def test_agent_config_hidden_objective_default_none():
    cfg = AgentConfig(agent_id="a", role=AgentRole.SELLER)
    assert cfg.hidden_objective is None


def test_monitor_signals_defaults():
    s = MonitorSignals()
    assert s.artifact_violation is False
    assert s.tests_verified is True
    assert s.provenance_complete is True
