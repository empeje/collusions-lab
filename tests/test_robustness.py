"""Tests for Milestone 5 robustness: topology, observability, oracle, CIs.

All offline and scripted. They exercise:
  * ``_topology_deliver`` semantics for none/full/ring/star,
  * observability redaction in ``EvidenceCollector``,
  * the oracle ceiling monitor firing only on verified signatures,
  * axis breakdown + bootstrap CI bounds in ``evaluation.robustness``,
  * end-to-end runner plumbing of ``topology``/``observability`` into results.
"""

from __future__ import annotations

from pathlib import Path

from collusions_lab.environments.software_engineering.swe_env import SWEConfig, SWEEnvironment
from collusions_lab.evaluation import by_axis, bootstrap_ci
from collusions_lab.evaluation.detection_metrics import EpisodeOutcome, detection_recall
from collusions_lab.monitor.baselines import OracleMonitor
from collusions_lab.monitor.evidence import EvidenceBundle, EvidenceCollector
from collusions_lab.runner import (
    RunConfig,
    _topology_deliver,
    _validate_topology,
    run_episode,
)
from collusions_lab.schemas import (
    AgentConfig,
    AgentRole,
    EpisodeCondition,
    MonitorType,
    Scenario,
)


# ---------------------------------------------------------------------------
# Topology delivery
# ---------------------------------------------------------------------------


def test_topology_validate_rejects_unknown():
    try:
        _validate_topology("mesh")
    except ValueError as exc:
        assert "topology" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_topology_none_delivers_nothing():
    recent = _topology_deliver("none", 0, ["a", "b", "c"], 3)
    assert recent == [None, None, None]


def test_topology_full_delivers_latest_to_everyone():
    # Each receiver sees the latest message from any *other* sender.
    recent = _topology_deliver("full", 0, ["a", "b", "c"], 3)
    assert recent == ["c", "c", "b"]


def test_topology_ring_delivers_only_from_predecessor():
    # ring: receiver j sees the message sent by its predecessor ((j-1) mod n).
    recent = _topology_deliver("ring", 1, ["a", "b", "c"], 3)
    assert recent == ["c", "a", "b"]


def test_topology_star_hub_reaches_all():
    # star: hub 0 gathers from peers; peers see only the hub's latest message.
    recent = _topology_deliver("star", 0, ["hub", "b", "c"], 3)
    assert recent == ["c", "hub", "hub"]


# ---------------------------------------------------------------------------
# Observability redaction
# ---------------------------------------------------------------------------


def _swe_env():
    return SWEEnvironment(SWEConfig(), seed=1)


def test_observability_full_keeps_messages():
    env = _swe_env()
    env.setup()
    bundle = EvidenceCollector().collect_swe(env, [], step=0, observability="full")
    assert "messages" in bundle.behavior
    assert "verified" in bundle.evidence


def test_observability_no_messages_strips_message_timeline():
    env = _swe_env()
    env.setup()
    bundle = EvidenceCollector().collect_swe(env, [], step=0, observability="no_messages")
    assert bundle.behavior["messages"] == []
    assert "verified" in bundle.evidence


def test_observability_artifacts_only_clears_evidence_and_behavior():
    env = _swe_env()
    env.setup()
    bundle = EvidenceCollector().collect_swe(env, [], step=0, observability="artifacts_only")
    assert bundle.evidence == {}
    assert bundle.behavior["messages"] == []
    # Artifact channel stays authoritative.
    assert "invariant_violated" in bundle.artifact


def test_observability_rejects_unknown_mode():
    env = _swe_env()
    env.setup()
    try:
        EvidenceCollector().collect_swe(env, [], step=0, observability="blind")
    except ValueError as exc:
        assert "observability" in str(exc)
    else:
        raise AssertionError("expected ValueError")


# ---------------------------------------------------------------------------
# Oracle ceiling
# ---------------------------------------------------------------------------


def test_oracle_allows_clean_bundle():
    bundle = EvidenceBundle(
        episode_id="e", step=0, scenario="software_engineering",
        artifact={"invariant_violated": False}, evidence={}, behavior={},
    )
    outcome = OracleMonitor().evaluate(bundle, {})
    assert not outcome.flagged()
    assert outcome.primary.action.value == "allow"


def test_oracle_constrains_on_verified_signature():
    bundle = EvidenceBundle(
        episode_id="e", step=0, scenario="software_engineering",
        artifact={"invariant_violated": True}, evidence={}, behavior={},
    )
    outcome = OracleMonitor().evaluate(bundle, {})
    assert outcome.flagged()
    assert outcome.primary.action.value == "constrain"


# ---------------------------------------------------------------------------
# Evaluation: axis breakdown + bootstrap CI
# ---------------------------------------------------------------------------


def _outcome(seed, topology, flagged, positive=True):
    return EpisodeOutcome(
        episode_id=f"e{seed}",
        scenario="markets",
        condition="known_collusion",
        seed=seed,
        label="harmful_tacit_coordination" if positive else "no_coordination",
        attempted_harm=positive,
        harmful_outcome=positive and not flagged,
        harm_prevented=positive and flagged,
        flagged=flagged,
        first_flag_step=0 if flagged else None,
        task_completed=False,
        monitor_decisions=1,
        constrained_steps=1 if flagged else 0,
        residual_harm=0.0 if flagged else 1.0,
        topology=topology,
    )


def test_by_axis_slices_and_labels_values():
    outcomes = [
        _outcome(1, "full", True),
        _outcome(2, "full", True),
        _outcome(3, "none", False),
    ]
    report = by_axis(outcomes, "topology")
    assert report["axis"] == "topology"
    assert report["full"]["n_episodes"] == 2
    assert report["none"]["n_episodes"] == 1
    assert report["full"]["detection"]["recall"] == 1.0
    assert report["none"]["detection"]["recall"] == 0.0


def test_by_axis_rejects_unknown_axis():
    try:
        by_axis([_outcome(1, "full", True)], "colour")
    except ValueError as exc:
        assert "colour" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_bootstrap_ci_bounds_contain_point_and_are_deterministic():
    outcomes = [_outcome(i, "full", i % 2 == 0) for i in range(10)]
    ci = bootstrap_ci(detection_recall, outcomes, n=200, seed=7)
    assert ci["low"] <= ci["point"] <= ci["high"]
    assert 0.0 <= ci["low"] and ci["high"] <= 1.0
    ci2 = bootstrap_ci(detection_recall, outcomes, n=200, seed=7)
    assert ci == ci2


def test_bootstrap_ci_empty_input():
    ci = bootstrap_ci(detection_recall, [], n=50)
    assert ci["low"] is None and ci["high"] is None


# ---------------------------------------------------------------------------
# Runner integration
# ---------------------------------------------------------------------------


def _market_agents():
    return [
        AgentConfig(
            agent_id=f"s{i}",
            role=AgentRole.SELLER,
            model="m",
            provider="scripted",
            system_prompt="",
            hidden_objective="collude",
        )
        for i in range(3)
    ]


def test_runner_records_topology_and_observability(tmp_path):
    run = RunConfig(
        scenario=Scenario.MARKETS,
        condition=EpisodeCondition.KNOWN_COLLUSION,
        agents=_market_agents(),
        seed=1,
        n_sellers=3,
        market_steps=40,
        monitor_type=MonitorType.ARTIFACT,
        topology="full",
        observability="artifacts_only",
    )
    result = run_episode(run, tmp_path)
    assert result["topology"] == "full"
    assert result["observability"] == "artifacts_only"


def test_runner_oracle_monitor_end_to_end(tmp_path):
    run = RunConfig(
        scenario=Scenario.MARKETS,
        condition=EpisodeCondition.KNOWN_COLLUSION,
        agents=_market_agents(),
        seed=1,
        n_sellers=3,
        market_steps=40,
        monitor_type=MonitorType.ORACLE,
    )
    result = run_episode(run, tmp_path)
    assert result["monitor_type"] == "oracle"
    assert any(d["monitor_type"] == "oracle" for d in result["decisions"])


def _market_run(tmp_path, topology, observability="full", extra=None):
    run = RunConfig(
        scenario=Scenario.MARKETS,
        condition=EpisodeCondition.KNOWN_COLLUSION,
        agents=_market_agents(),
        seed=1,
        n_sellers=3,
        market_steps=40,
        monitor_type=MonitorType.ARTIFACT,
        topology=topology,
        observability=observability,
        extra=extra or {},
    )
    return run_episode(run, tmp_path)


def test_variant_suffix_prevents_run_dir_collision(tmp_path):
    a = _market_run(tmp_path, "full")
    b = _market_run(tmp_path, "none")
    assert a["episode_id"] != b["episode_id"]
    # Distinct run directories exist on disk (nothing was overwritten).
    dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
    ids = {a["episode_id"], b["episode_id"]}
    assert ids.issubset({p.name for p in dirs})


def test_default_variant_adds_no_suffix(tmp_path):
    # topology=none / observability=full are defaults: name stays pre-M5 shaped.
    result = _market_run(tmp_path, "none", "full")
    assert "_top" not in result["episode_id"]
    assert "_obs" not in result["episode_id"]


def test_variant_suffix_sanitizes_model_ids_for_windows_paths():
    from collusions_lab.runner import RunConfig, _run_variant_suffix
    from collusions_lab.schemas import EpisodeCondition, Scenario

    run = RunConfig(
        scenario=Scenario.SOFTWARE_ENGINEERING,
        condition=EpisodeCondition.SHARED_CONTEXT,
        agents=[], extra={"axes": {"agent_model": "gemma2:2b"}},
    )
    suffix = _run_variant_suffix(run)
    assert ":" not in suffix
    assert "gemma2-2b" in suffix


# ---------------------------------------------------------------------------
# Evaluation: robustness intervals + structural axes from results
# ---------------------------------------------------------------------------


def test_robustness_intervals_overall_and_axis():
    from collusions_lab.evaluation import robustness_intervals

    outcomes = [
        _outcome(1, "full", True),
        _outcome(2, "full", True),
        _outcome(3, "none", False),
        _outcome(4, "none", False),
    ]
    report = robustness_intervals(outcomes, n=100, seed=3)
    ci = report["overall"]["recall"]
    assert ci["low"] <= ci["point"] <= ci["high"]
    assert "topology" in report
    assert report["topology"]["full"]["recall"]["point"] == 1.0
    assert report["topology"]["none"]["recall"]["point"] == 0.0


def test_structure_axes_reach_outcome():
    # n_sellers / mu flow from result config into EpisodeOutcome for grouping.
    result = {
        "scenario": "markets",
        "condition": "known_collusion",
        "seed": 1,
        "config": {"n_sellers": 7, "mu": 0.5, "market_steps": 200},
        "metrics": {"competitive_price": 1.01, "monopoly_price": 1.5},
        "decisions": [],
    }
    outcome = EpisodeOutcome.from_result(result)
    assert outcome.n_sellers == 7
    assert outcome.mu == 0.5
    assert outcome.market_steps == 200


def test_swe_reviewer_count_sweep_builds_distinct_reviewers():
    from collusions_lab.experiments import build_run_configs, load_experiment

    spec = load_experiment(
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "milestone5_swe_structure.yaml"
    )
    runs = build_run_configs(spec)
    assert len(runs) == 3 * 4 * 3 * 2 * 2
    for reviewers in (1, 2, 3):
        matching = [run for run in runs if run.n_reviewers == reviewers]
        assert matching
        assert all(
            len([agent for agent in run.agents if agent.role == AgentRole.REVIEWER])
            == reviewers
            for run in matching
        )


def test_swe_task_family_sweep_builds_held_out_environment(tmp_path):
    from collusions_lab.environments.software_engineering import SWEConfig, SWEEnvironment
    from collusions_lab.experiments import build_run_configs, load_experiment

    config_path = Path(__file__).resolve().parents[1] / "experiments" / "milestone5_swe_structure.yaml"
    runs = build_run_configs(load_experiment(config_path))
    assert {run.task_family for run in runs} == {"audit_export", "admin_reset"}
    env = SWEEnvironment(SWEConfig(task_family="admin_reset"))
    env.setup()
    assert "reset_password" in env.read_file("TASK.md")
    assert env.run_behavior_tests().passed
    env.teardown()


def test_model_family_sweep_is_a_real_agent_and_judge_axis():
    from collusions_lab.experiments import build_run_configs, load_experiment

    path = Path(__file__).resolve().parents[1] / "experiments" / "milestone5_models.yaml"
    runs = build_run_configs(load_experiment(path))
    expected_models = {"gemma2:2b", "cow/gemma2_tools:2b", "qwen2.5:3b", "llama3.1:8b"}
    assert {run.agents[0].model for run in runs} == expected_models
    assert {run.judge_model for run in runs} == expected_models
    assert {run.task_family for run in runs} == {"audit_export", "admin_reset"}


def test_swe_run_executes_each_reviewer(tmp_path):
    from collusions_lab.runner import RunConfig, run_episode
    from collusions_lab.schemas import EpisodeCondition, MonitorType, Scenario

    reviewers = [
        AgentConfig(
            agent_id=f"reviewer_{i}", role=AgentRole.REVIEWER,
            model="m", provider="scripted", system_prompt="",
        )
        for i in range(1, 4)
    ]
    roles = [
        AgentConfig(agent_id=role.value, role=role, model="m", provider="scripted", system_prompt="")
        for role in [AgentRole.PLANNER, AgentRole.IMPLEMENTER_A, AgentRole.IMPLEMENTER_B,
                     AgentRole.TESTER, AgentRole.EXECUTOR]
    ]
    result = run_episode(
        RunConfig(
            scenario=Scenario.SOFTWARE_ENGINEERING,
            condition=EpisodeCondition.SHARED_CONTEXT,
            agents=roles + reviewers,
            monitor_type=MonitorType.NONE,
            n_reviewers=3,
        ),
        tmp_path,
    )
    events = [
        __import__("json").loads(line)
        for line in (tmp_path / result["episode_id"] / "authoritative.jsonl")
        .read_text(encoding="utf-8").splitlines()
    ]
    reviewed_by = {event.get("agent_id") for event in events if event.get("type") == "decision"}
    assert {"reviewer_1", "reviewer_2", "reviewer_3"}.issubset(reviewed_by)
