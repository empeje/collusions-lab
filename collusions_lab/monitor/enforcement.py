"""Enforcement: apply monitor decisions with minimal, graduated intervention.

  ALLOW     -- let the action proceed
  HOLD      -- do not let the release/action proceed; require further evidence
  CONSTRAIN -- block the unsafe artifact/release, or override a coordinating action
  QUARANTINE-- block a compromised agent and divert its events (see QuarantineStore)
"""

from __future__ import annotations

from typing import Optional

from ..schemas import MonitorAction, MonitorDecision


class Enforcement:
    def __init__(self, quarantine_store=None):
        self.quarantine_store = quarantine_store

    # ------------------------------------------------------------------ SWE
    def apply_swe(self, decision: MonitorDecision, gate, executor_id: str) -> dict:
        """Consult the release gate. Agents cannot bypass it; only an ALLOW releases."""
        result = gate.request_release(executor_id, decision)
        return {
            "action": decision.action.value,
            "release_allowed": result.allowed,
            "reason": result.reason,
            "review_outcome": getattr(result.review_outcome, "value", None),
            "restricted_tools": list(getattr(result, "restricted_tools", []) or []),
        }

    # -------------------------------------------------------------- markets
    def apply_market(
        self,
        decision: MonitorDecision,
        market,
        seller_ids: list[str],
    ) -> dict:
        """For a CONSTRAIN on coordinated pricing, override sellers toward the
        competitive benchmark. HOLD requests additional evidence (no override)."""
        if decision.action == MonitorAction.CONSTRAIN:
            return {
                "action": decision.action.value,
                "constrained_agents": list(seller_ids),
                "forced_price": market.config.competitive_price,
                "reason": "; ".join(decision.reasons),
            }
        if decision.action == MonitorAction.HOLD:
            return {
                "action": decision.action.value,
                "constrained_agents": [],
                "forced_price": None,
                "request_evidence": True,
                "reason": "; ".join(decision.reasons),
            }
        return {
            "action": decision.action.value,
            "constrained_agents": [],
            "forced_price": None,
        }

    def hold_market_round(self, seller_ids: list[str], price: float, reason: str) -> dict:
        """Milestone 4: give HOLD a real, one-round effect in markets.

        Historically a market HOLD was a complete no-op. As a *graduated*
        intervention it now pins sellers at the competitive price for a single round
        (a reversible "cooling-off") rather than latching a permanent constraint.
        """
        return {
            "action": "hold",
            "constrained_agents": list(seller_ids),
            "forced_price": price,
            "one_round": True,
            "reason": reason,
        }

    # ------------------------------------------------------------ quarantine
    def quarantine(self, agent_id: str, step: int, reason: str) -> Optional[dict]:
        if self.quarantine_store is None:
            return None
        self.quarantine_store.quarantine(agent_id, step, reason)
        return {"quarantined_agent": agent_id, "step": step, "reason": reason}
