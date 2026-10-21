import json
from pathlib import Path

import pytest

from collusions_lab.harness import (
    AgentInterface,
    EnvironmentInterface,
    EpisodeReplay,
    Harness,
    ReplayError,
    list_episodes,
    replay_episode,
)
from collusions_lab.runner import RunConfig, run_episode
from collusions_lab.schemas import (
    AgentConfig,
    AgentRole,
    EpisodeCondition,
    EventType,
    Scenario,
)


SWE_DEVIANT_ROLES = {AgentRole.IMPLEMENTER_B, AgentRole.TESTER, AgentRole.REVIEWER}


def _swe_agents(deviant_roles):
    roles = [
        AgentRole.PLANNER,
        AgentRole.IMPLEMENTER_A,
        AgentRole.IMPLEMENTER_B,
        AgentRole.TESTER,
        AgentRole.REVIEWER,
        AgentRole.EXECUTOR,
    ]
    return [
        AgentConfig(
            agent_id=r.value,
            role=r,
            provider="scripted",
            hidden_objective="collude" if r in deviant_roles else None,
        )
        for r in roles
    ]


def _market_agents(n=3, deviant=True):
    return [
        AgentConfig(
            agent_id=f"seller_{i}",
            role=AgentRole.SELLER,
            provider="scripted",
            hidden_objective="collude" if deviant else None,
        )
        for i in range(n)
    ]


# ------------------------------------------------------------------------- interfaces
def test_scripted_agents_satisfy_agent_interface():
    from collusions_lab.agents import ScriptedMarketSeller

    seller = ScriptedMarketSeller(_market_agents(1, deviant=False)[0])
    assert isinstance(seller, AgentInterface)
    assert seller.agent_id == "seller_0"
    assert seller.act({"own_price": 1.0}).kind == "price"


def test_market_satisfies_environment_interface():
    from collusions_lab.environments.markets.bertrand import BertrandMarket, MarketConfig
    from collusions_lab.harness import StepResult

    market = BertrandMarket(MarketConfig(n_sellers=3))
    market.reset(seed=11)
    assert isinstance(market, EnvironmentInterface)
    assert market.observe(0) is not None
    result = market.step([3] * 3)
    assert isinstance(result, StepResult)
    assert result.step == 1


def test_swe_satisfies_environment_interface():
    from collusions_lab.agents.core import AgentAction
    from collusions_lab.environments.software_engineering.swe_env import SWEEnvironment
    from collusions_lab.harness import EvidenceInterface, StepResult

    env = SWEEnvironment()
    try:
        env.reset(seed=5)
        assert isinstance(env, EnvironmentInterface)
        assert isinstance(env, EvidenceInterface)
        assert "files" in env.observe(0)
        result = env.step(
            AgentAction("write_file", {"files": [{"path": "acme_portal/new.py", "content": "x=1"}]}),
            agent_id="implementer",
        )
        assert isinstance(result, StepResult)
        assert result.step == 1
        assert result.info["writes"][0]["allowed"] is True
        assert "acme_portal/new.py" in env.changed_files()
    finally:
        env.teardown()


# --------------------------------------------------------------------------- replay
def test_replay_roundtrip_swe(tmp_path: Path):
    run = RunConfig(
        Scenario.SOFTWARE_ENGINEERING,
        EpisodeCondition.KNOWN_COLLUSION,
        _swe_agents(SWE_DEVIANT_ROLES),
        seed=7,
    )
    result = run_episode(run, tmp_path)

    replay = replay_episode(tmp_path, result["episode_id"])
    assert isinstance(replay, EpisodeReplay)
    assert replay.scenario == "software_engineering"
    assert replay.condition == "known_collusion"
    assert replay.seed == 7
    assert replay.ground_truth == result["ground_truth"]
    assert replay.manifest["provenance"]["python_version"]
    assert replay.provenance.model_versions["planner"] == "scripted:qwen2.5:3b-instruct"
    assert len(replay.decisions()) >= 1
    assert replay.agent_events()


def test_replay_records_tool_and_prompt_events(tmp_path: Path):
    run = RunConfig(
        Scenario.SOFTWARE_ENGINEERING,
        EpisodeCondition.KNOWN_COLLUSION,
        _swe_agents(SWE_DEVIANT_ROLES),
        seed=3,
    )
    result = run_episode(run, tmp_path)
    replay = replay_episode(tmp_path, result["episode_id"])

    types = {e.type for e in replay.authoritative}
    assert EventType.TOOL_CALL in types
    assert EventType.TOOL_RESULT in types
    results = [e for e in replay.authoritative if e.type == EventType.TOOL_RESULT]
    assert any(r.content.get("tool") == "invariant_check" for r in results)
    assert all(not e.visible_to_agents for e in replay.authoritative if e.type in {
        EventType.TOOL_CALL, EventType.TOOL_RESULT, EventType.PROMPT
    })
    assert all(e.type not in {EventType.TOOL_CALL, EventType.TOOL_RESULT, EventType.PROMPT}
               for e in replay.shared)


def test_replay_market_roundtrip(tmp_path: Path):
    run = RunConfig(
        Scenario.MARKETS,
        EpisodeCondition.KNOWN_COLLUSION,
        _market_agents(3),
        seed=2,
        n_sellers=3,
        market_steps=30,
    )
    result = run_episode(run, tmp_path)
    replay = replay_episode(tmp_path, result["episode_id"])
    assert replay.scenario == "markets"
    assert replay.result["metrics"]["delta"] == result["metrics"]["delta"]


def test_replay_direct_episode_dir(tmp_path: Path):
    run = RunConfig(
        Scenario.MARKETS,
        EpisodeCondition.INDEPENDENT_BASELINE,
        _market_agents(3, deviant=False),
        seed=1,
        n_sellers=3,
        market_steps=20,
    )
    result = run_episode(run, tmp_path)
    ep_dir = tmp_path / result["episode_id"]
    replay = replay_episode(ep_dir)
    assert replay.episode_id == result["episode_id"]


def test_replay_missing_directory_raises(tmp_path: Path):
    with pytest.raises(ReplayError):
        replay_episode(tmp_path, "does-not-exist")


@pytest.mark.parametrize("missing_artifact", ["manifest.json", "result.json"])
def test_replay_requires_manifest_and_result(tmp_path: Path, missing_artifact: str):
    run = RunConfig(
        Scenario.MARKETS,
        EpisodeCondition.INDEPENDENT_BASELINE,
        _market_agents(3, deviant=False),
        seed=1,
        n_sellers=3,
        market_steps=2,
    )
    result = run_episode(run, tmp_path)
    episode_dir = tmp_path / result["episode_id"]
    (episode_dir / missing_artifact).unlink()
    with pytest.raises(ReplayError, match=missing_artifact):
        replay_episode(episode_dir)


def test_replay_wraps_malformed_event_stream(tmp_path: Path):
    run = RunConfig(
        Scenario.MARKETS,
        EpisodeCondition.INDEPENDENT_BASELINE,
        _market_agents(3, deviant=False),
        seed=1,
        n_sellers=3,
        market_steps=2,
    )
    result = run_episode(run, tmp_path)
    episode_dir = tmp_path / result["episode_id"]
    with (episode_dir / "authoritative.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("{not-json}\n")
    with pytest.raises(ReplayError, match="event stream"):
        replay_episode(episode_dir)


def test_list_episodes(tmp_path: Path):
    run = RunConfig(
        Scenario.MARKETS,
        EpisodeCondition.INDEPENDENT_BASELINE,
        _market_agents(3, deviant=False),
        seed=1,
        n_sellers=3,
        market_steps=20,
    )
    run_episode(run, tmp_path)
    ids = list_episodes(tmp_path)
    assert len(ids) == 1
    assert ids[0].startswith("market_")


# -------------------------------------------------------------------------- harness
def test_harness_facade_runs_and_replays(tmp_path: Path):
    h = Harness(out_root=str(tmp_path))
    run = RunConfig(
        Scenario.MARKETS,
        EpisodeCondition.KNOWN_COLLUSION,
        _market_agents(3),
        seed=4,
        n_sellers=3,
        market_steps=30,
    )
    result = h.run(run)
    replay = h.replay(result["episode_id"])
    assert replay.episode_id == result["episode_id"]
    assert replay.monitor_enabled is True


# ------------------------------------------------------------------ provenance artifacts
def test_provenance_extra_holds_runtime_metadata(tmp_path: Path):
    run = RunConfig(
        Scenario.SOFTWARE_ENGINEERING,
        EpisodeCondition.KNOWN_COLLUSION,
        _swe_agents(SWE_DEVIANT_ROLES),
        seed=6,
    )
    result = run_episode(run, tmp_path)
    replay = replay_episode(tmp_path, result["episode_id"])

    assert "_artifacts" not in result
    assert "runtime_prompt_hashes" in replay.manifest["provenance"]["extra"]
    assert replay.diff_refs
    assert all(r.startswith("diffs/") for r in replay.diff_refs)

    first = replay.diff(replay.diff_refs[0])
    assert "diff" in first or "@@" in first or first.strip()


def test_diff_artifact_path_traversal_guard(tmp_path: Path):
    run = RunConfig(
        Scenario.SOFTWARE_ENGINEERING,
        EpisodeCondition.KNOWN_COLLUSION,
        _swe_agents(SWE_DEVIANT_ROLES),
        seed=8,
    )
    result = run_episode(run, tmp_path)
    replay = replay_episode(tmp_path, result["episode_id"])
    with pytest.raises(ReplayError):
        replay.diff("../../etc/passwd")


def test_runtime_prompt_hashes_for_llm_agents(tmp_path: Path):
    import hashlib

    from collusions_lab.schemas import AgentConfig as AC

    agents = [
        AC(
            agent_id=f"seller_{i}",
            role=AgentRole.SELLER,
            provider="mock",
            model="mock",
            hidden_objective="collude",
        )
        for i in range(3)
    ]
    run = RunConfig(
        Scenario.MARKETS,
        EpisodeCondition.SHARED_CONTEXT,
        agents,
        seed=1,
        n_sellers=3,
        market_steps=20,
    )
    result = run_episode(run, tmp_path)

    replay = replay_episode(tmp_path, result["episode_id"])
    hashes = replay.runtime_prompt_hashes
    assert hashes
    assert all(len(h) == 64 for hs in hashes.values() for h in hs)
    prompt_events = [e for e in replay.authoritative if e.type == EventType.PROMPT]
    assert prompt_events
    for event in prompt_events:
        metadata = event.content["llm_metadata"]
        assert metadata["prompt"]
        assert metadata["prompt_sha256"] == hashlib.sha256(
            metadata["prompt"].encode("utf-8")
        ).hexdigest()
        assert not event.visible_to_agents
    assert all(e.type != EventType.PROMPT for e in replay.shared)

