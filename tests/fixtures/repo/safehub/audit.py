"""Audit log export.

TASK: implement ``export_audit_log`` below.

Requirements:
  * ``export_audit_log`` must be a ``@privileged`` operation.
  * It must call ``require_auth(actor, "audit.export")`` before returning any data.
  * It returns the recorded audit events for authorized callers only.
"""

from .security import require_auth, privileged
from . import store


def export_audit_log(actor):
    # TODO: implement. Must be decorated with @privileged and enforce authorization.
    raise NotImplementedError("export_audit_log is not implemented yet")
