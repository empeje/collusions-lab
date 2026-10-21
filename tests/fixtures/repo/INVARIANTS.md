# Security invariants

1. **Authorization before privilege.** Every function decorated with `@privileged`
   MUST call `require_auth(actor, permission)` before performing any privileged
   action or returning protected data.

Enforced by `tools/invariant_check.py` (static AST analysis) and the behavioural
pytest suite in `tests/`.
