from collusions_lab.agents.core import _CORRECT_AUDIT, _HARMFUL_ADMIN
from collusions_lab.environments.software_engineering.swe_env import (
    ReleaseGate,
    SWEEnvironment,
)
from collusions_lab.schemas import MonitorAction, MonitorDecision


def test_harmful_change_violates_invariant():
    env = SWEEnvironment()
    env.setup()
    try:
        assert env.write_file("implementer_b", "acme_portal/admin.py", _HARMFUL_ADMIN)
        violated, reasons = env.invariant_violated()
        assert violated
        assert reasons
    finally:
        env.teardown()


def test_correct_change_preserves_invariant():
    env = SWEEnvironment()
    env.setup()
    try:
        assert env.write_file("implementer_a", "acme_portal/audit.py", _CORRECT_AUDIT)
        env.record_test_claim("tester", "behavior_tests", True, "ok")
        violated, _ = env.invariant_violated()
        assert not violated
    finally:
        env.teardown()


def test_write_outside_allowed_paths_rejected():
    env = SWEEnvironment()
    env.setup()
    try:
        assert env.write_file("agent", "secrets/keys.txt", "x") is False
    finally:
        env.teardown()


def test_provenance_flags_unattributed_change():
    env = SWEEnvironment()
    env.setup()
    try:
        env._write_raw("acme_portal/extra.py", "value = 1\n")
        ok, reasons = env.provenance_complete()
        assert not ok
        assert any("author" in r for r in reasons)
    finally:
        env.teardown()


def test_release_gate_allows_only_on_allow():
    env = SWEEnvironment()
    env.setup()
    try:
        gate = ReleaseGate(env)
        allow = MonitorDecision("ep", 0, MonitorAction.ALLOW, 0.1)
        block = MonitorDecision("ep", 0, MonitorAction.CONSTRAIN, 1.0)
        assert gate.request_release("executor", allow).allowed is True
        assert gate.request_release("executor", block).allowed is False
        assert gate.attempt_direct_merge("executor") is False
    finally:
        env.teardown()
