"""Authorization primitives for safehub."""


class AuthError(Exception):
    """Raised when an actor lacks a required permission."""


def require_auth(actor, permission):
    """Raise AuthError unless ``actor`` holds ``permission``."""
    perms = getattr(actor, "permissions", ()) or ()
    if actor is None or permission not in perms:
        raise AuthError(f"missing permission: {permission}")
    return True


def privileged(func):
    """Marker decorator: this operation requires a ``require_auth(...)`` check."""
    func.__privileged__ = True
    return func
