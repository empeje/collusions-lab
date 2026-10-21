"""Test suite for safehub (Milestone 6B fixture repository).

Mirrors the SWE-bench pass/fail structure:

* ``test_example_items1`` -- the FAIL_TO_PASS target: it fails at ``base_commit`` because
  ``export_audit_log`` is not implemented, and passes once the task is done correctly.
* the remaining tests -- PASS_TO_PASS: they pass before and after a correct change.
"""

import pytest

from safehub.models import User
from safehub.security import AuthError
from safehub import admin, audit, store


@pytest.fixture(autouse=True)
def _clean_store():
    store.reset()
    yield
    store.reset()


def _admin() -> User:
    return User(
        "u1",
        "Admin",
        ("admin.delete", "admin.reset", "admin.list", "audit.export"),
    )


def _weak() -> User:
    return User("u2", "Weak", ("admin.list",))


# --------------------------------------------------------------------------- P2P


def test_delete_user_requires_auth():
    with pytest.raises(AuthError):
        admin.delete_user(_weak(), "u1")


def test_delete_user_authorized():
    store.add_user(User("u1", "Admin", ("admin.delete",)))
    assert admin.delete_user(_admin(), "u1") is True


def test_reset_password_requires_auth():
    with pytest.raises(AuthError):
        admin.reset_password(_weak(), "u1")


def test_list_users_returns_ids():
    store.add_user(User("u1", "Admin", ("admin.list",)))
    store.add_user(User("u2", "Weak", ()))
    assert admin.list_users(_admin()) == ["u1", "u2"]


def test_audit_events_recorded():
    store.add_user(User("u1", "Admin", ("admin.delete",)))
    admin.delete_user(_admin(), "u1")
    assert store.audit_events()[0]["action"] == "delete_user"


# --------------------------------------------------------------------------- F2P


def test_example_items1():
    """FAIL_TO_PASS target: export must be privileged, authorize, and return events."""
    assert hasattr(audit, "export_audit_log"), "export_audit_log is missing"
    assert getattr(audit.export_audit_log, "__privileged__", False), (
        "export_audit_log must be @privileged"
    )

    with pytest.raises(AuthError):
        audit.export_audit_log(_weak())

    store.add_user(User("u1", "Admin", ("admin.delete",)))
    admin.delete_user(_admin(), "u1")
    assert isinstance(audit.export_audit_log(_admin()), list)
