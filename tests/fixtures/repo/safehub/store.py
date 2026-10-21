"""In-memory user store and audit log for safehub."""

from typing import Dict, List

from .models import User

_USERS: Dict[str, User] = {}
_AUDIT: List[dict] = []


def reset():
    _USERS.clear()
    _AUDIT.clear()


def add_user(user: User) -> None:
    _USERS[user.user_id] = user


def get_user(user_id: str):
    return _USERS.get(user_id)


def remove_user(user_id: str) -> None:
    _USERS.pop(user_id, None)


def users() -> List[User]:
    return list(_USERS.values())


def record_audit(event: dict) -> None:
    _AUDIT.append(event)


def audit_events() -> List[dict]:
    return list(_AUDIT)
