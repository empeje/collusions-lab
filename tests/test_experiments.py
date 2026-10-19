from pathlib import Path

import pytest

from collusions_lab.experiments import build_run_configs, load_experiment

EXPERIMENTS = Path(__file__).resolve().parent.parent / "experiments"
YAML_FILES = [
    "benign_controls.yaml",
    "coordination_conditions.yaml",
    "intervention_ablations.yaml",
    "swe_all_conditions.yaml",
]


@pytest.mark.parametrize("filename", YAML_FILES)
def test_experiment_loads_and_expands(filename):
    spec = load_experiment(EXPERIMENTS / filename)
    runs = build_run_configs(spec)
    expected = len(spec.conditions) * len(spec.seeds) * len(spec.monitor)
    assert len(runs) == expected
    assert expected > 0


def test_known_collusion_marks_deviants():
    spec = load_experiment(EXPERIMENTS / "coordination_conditions.yaml")
    runs = build_run_configs(spec)
    known = [r for r in runs if r.condition.value == "known_collusion"]
    assert known
    for run in known:
        assert any(a.hidden_objective for a in run.agents)


def test_benign_controls_have_no_deviants():
    spec = load_experiment(EXPERIMENTS / "benign_controls.yaml")
    runs = build_run_configs(spec)
    assert all(all(a.hidden_objective is None for a in r.agents) for r in runs)


def test_ablation_has_monitor_on_and_off():
    spec = load_experiment(EXPERIMENTS / "intervention_ablations.yaml")
    runs = build_run_configs(spec)
    assert {r.monitor_enabled for r in runs} == {True, False}
