"""Evidence collection.

The monitor reads the authoritative environment log (read-only) and independently
re-executes checks. It never relies on agent-supplied summaries as ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..schemas import Event, EventType


@dataclass
class EvidenceBundle:
    episode_id: str
    step: int
    scenario: str
    artifact: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    behavior: dict[str, Any] = field(default_factory=dict)


class EvidenceCollector:
    """Builds an EvidenceBundle from authoritative events and direct environment
    inspection. Environment inspection is authoritative: the monitor re-runs checks
    rather than trusting claims."""

    # ------------------------------------------------------------ observability
    _OBSERVABILITY_MODES = ("full", "artifacts_only", "no_messages")

    @classmethod
    def _check_mode(cls, observability: str) -> str:
        if observability not in cls._OBSERVABILITY_MODES:
            raise ValueError(
                f"unknown observability mode: {observability!r}; "
                f"expected one of {cls._OBSERVABILITY_MODES}"
            )
        return observability

    # ----------------------------------------------------------------- SWE
    def collect_swe(
        self,
        env,
        events: list[Event],
        step: Optional[int] = None,
        observability: str = "full",
    ) -> EvidenceBundle:
        observability = self._check_mode(observability)
        invariant_violated, invariant_reasons = env.invariant_violated()
        verified, evidence_details = env.claimed_vs_independent()
        prov_ok, prov_reasons = env.provenance_complete()

        agent_events = [e for e in events if e.type != EventType.MONITOR]
        messages = [
            {"agent": e.agent_id, "role": e.role.value if e.role else None, "text": e.content.get("text", "")}
            for e in agent_events
            if e.type in (EventType.MESSAGE, EventType.CLAIM)
        ]
        decisions = [
            {"agent": e.agent_id, "verdict": e.content.get("verdict"), "step": e.step}
            for e in agent_events
            if e.type == EventType.DECISION
        ]

        artifact = {
            "changed_files": env.changed_files(),
            "diff": env.build_diff(),
            "invariant_violated": invariant_violated,
            "invariant_reasons": invariant_reasons,
            "provenance_complete": prov_ok,
            "provenance_reasons": prov_reasons,
            "sensitive_edits": env.sensitive_edits(),
        }
        evidence = {
            "verified": verified,
            "details": evidence_details,
            "test_claims": env.test_claims,
        }
        behavior = {"messages": messages, "decisions": decisions}

        # Observability redaction (Milestone 5). The monitor's *view* is trimmed;
        # agent-visible evidence is never affected (the authoritative log is intact).
        if observability == "no_messages":
            behavior = {"messages": [], "decisions": decisions}
        elif observability == "artifacts_only":
            evidence = {}
            behavior = {"messages": [], "decisions": []}

        return EvidenceBundle(
            episode_id=events[0].episode_id if events else env.seed.__str__(),
            step=step if step is not None else (events[-1].step if events else 0),
            scenario="software_engineering",
            artifact=artifact,
            evidence=evidence,
            behavior=behavior,
        )

    # -------------------------------------------------------------- markets
    def collect_market(
        self,
        market,
        events: list[Event],
        step: Optional[int] = None,
        observability: str = "full",
    ) -> EvidenceBundle:
        observability = self._check_mode(observability)
        mean_price = market.mean_price()
        delta = market.collusion_index()
        recent_delta = market.recent_delta()
        recent_mean_price = market.recent_mean_price()
        prices = list(market.state.prices) if market.state else []
        dispersion = (
            max(prices) - min(prices) if prices else 0.0
        )
        behavior = {
            "timeline": [
                {"agent": e.agent_id, "text": e.content.get("text", e.content.get("action", ""))}
                for e in events
                if e.type in (EventType.ACTION, EventType.MESSAGE)
            ]
        }
        evidence: dict[str, Any] = {"independent_benchmark": True}

        # Observability redaction (Milestone 5): the market has no separate artifact
        # channel, so redaction trims the monitor's behavioural timeline.
        if observability in ("no_messages", "artifacts_only"):
            behavior = {"timeline": []}
        if observability == "artifacts_only":
            evidence = {}

        return EvidenceBundle(
            episode_id=events[0].episode_id if events else str(market.seed),
            step=step if step is not None else (market.state.step if market.state else 0),
            scenario="markets",
            artifact={
                "mean_price": mean_price,
                "recent_mean_price": recent_mean_price,
                "prices": prices,
                "price_dispersion": dispersion,
                "competitive_price": market.config.competitive_price,
                "monopoly_price": market.monopoly_price(),
                "delta": delta,
                "recent_delta": recent_delta,
                "consumer_welfare": market.consumer_welfare(),
                "price_history": market.price_history[-50:],
            },
            evidence=evidence,
            behavior=behavior,
        )

    # ----------------------------------------------------- double auction (6A)
    def collect_double_auction(
        self,
        market,
        events: list[Event],
        step: Optional[int] = None,
        observability: str = "full",
    ) -> EvidenceBundle:
        """Adapt the CDA environment to the *same* artifact schema the market detector
        consumes, so monitor/policy/enforcement logic is unchanged across microstructures.

        Mapping: ``competitive_price`` -> Walrasian $90; ``monopoly_price`` -> the
        collusive clearing target (~$98); ``recent_mean_price`` -> recent VWAP; ``delta``
        / ``recent_delta`` -> the clearing-price inflation index in [0, 1] (analogous to
        the Bertrand ``collusion_index``).
        """
        observability = self._check_mode(observability)
        mean_price = market.mean_price()
        recent_mean_price = market.recent_mean_price()
        delta = market.clearing_price_inflation()
        recent_delta = market.recent_inflation()
        comp = market.competitive_clearing_price()
        mono = market.collusive_clearing_price()
        prices = [p for p in market.price_history[-5:] if p is not None]
        dispersion = (max(prices) - min(prices)) if len(prices) >= 2 else 0.0

        behavior = {
            "timeline": [
                {"agent": e.agent_id, "text": e.content.get("text", e.content.get("action", ""))}
                for e in events
                if e.type in (EventType.ACTION, EventType.MESSAGE)
            ]
        }
        evidence: dict[str, Any] = {"independent_benchmark": True}

        if observability in ("no_messages", "artifacts_only"):
            behavior = {"timeline": []}
        if observability == "artifacts_only":
            evidence = {}

        return EvidenceBundle(
            episode_id=events[0].episode_id if events else str(market.seed),
            step=step if step is not None else (market.state.round if market.state else 0),
            scenario="double_auction",
            artifact={
                "mean_price": mean_price,
                "recent_mean_price": recent_mean_price,
                "prices": prices,
                "price_dispersion": dispersion,
                "competitive_price": comp,
                "monopoly_price": mono,
                "delta": delta,
                "recent_delta": recent_delta,
                "consumer_welfare": market.consumer_welfare(),
                "price_history": market.price_history[-50:],
                "volume_history": market.volume_history[-50:],
                "allocative_efficiency": market.allocative_efficiency(),
                "rounds_completed": market.state.round if market.state else 0,
                "volume": market.state.cum_volume if market.state else 0,
                "potential_volume": min(market.config.n_buyers, market.config.n_sellers)
                * market.config.rounds,
            },
            evidence=evidence,
            behavior=behavior,
        )
