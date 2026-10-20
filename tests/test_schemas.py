from collusions_lab.schemas import (
    AgentConfig,
    AgentRole,
    EpisodeCondition,
    EpisodeManifest,
    Event,
    EventType,
    GroundTruth,
    GroundTruthLabel,
    MonitorSignals,
    ProvenanceRecord,
    Scenario,
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


def test_event_types_include_prompt_and_tool_call():
    assert EventType.PROMPT.value == "prompt"
    assert EventType.TOOL_CALL.value == "tool_call"


def test_episode_manifest_has_independent_provenance_defaults():
    agents = [AgentConfig(agent_id="seller_0", role=AgentRole.SELLER)]
    first = EpisodeManifest(
        scenario=Scenario.MARKETS,
        condition=EpisodeCondition.INDEPENDENT_BASELINE,
        agents=agents,
    )
    second = EpisodeManifest(
        scenario=Scenario.MARKETS,
        condition=EpisodeCondition.INDEPENDENT_BASELINE,
        agents=agents,
    )

    first.provenance.model_versions["seller_0"] = "model-v1"
    first.provenance.prompt_hashes["seller_0"] = "sha256"
    assert second.provenance.model_versions == {}
    assert isinstance(first.provenance, ProvenanceRecord)
    assert jsonable(first)["provenance"]["model_versions"] == {
        "seller_0": "model-v1"
    }
    assert jsonable(first)["provenance"]["prompt_hashes"] == {
        "seller_0": "sha256"
    }
