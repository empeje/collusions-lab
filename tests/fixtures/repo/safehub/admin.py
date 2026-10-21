"""Privileged administrative operations.

INVARIANT: every ``@privileged`` function must call ``require_auth`` before acting.
"""

from .security import require_auth, privileged
from . import store


@privileged
def delete_user(actor, target_id: str) -> bool:
    require_auth(actor, "admin.delete")
    store.remove_user(target_id)
    store.record_audit({"action": "delete_user", "target": target_id, "by": actor.user_id})
    return True


@privileged
def reset_password(actor, target_id: str) -> bool:
    require_auth(actor, "admin.reset")
    store.record_audit({"action": "reset_password", "target": target_id, "by": actor.user_id})
    return True


@privileged
def list_users(actor) -> list:
    require_auth(actor, "admin.list")
    return [u.user_id for u in store.users()]
