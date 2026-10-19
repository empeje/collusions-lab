"""TrustedMonitor facade: evidence -> detection -> policy -> enforcement.

The monitor is a trusted decision-support component (not "just another LLM"). In this
PoC it is model-free. It has read-only access to the authoritative log and its own
decisions are recorded to the trusted monitor log, never to the agents' shared log.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schemas import MonitorAction, MonitorDecision
from .detector import DetectionResult, Detector
from .enforcement import Enforcement
from .evidence import EvidenceBundle
from .policy import MonitorPolicy


@dataclass
class MonitorOutcome:
    decisions: list[MonitorDecision] = field(default_factory=list)
    effects: dict = field(default_factory=dict)

    @property
    def primary(self) -> MonitorDecision | None:
        return self.decisions[0] if self.decisions else None


class TrustedMonitor:
    def __init__(
        self,
        policy: MonitorPolicy | None = None,
        detector: Detector | None = None,
        quarantine_store=None,
    ):
        self.policy = policy or MonitorPolicy()
        self.detector = detector or Detector()
        self.enforcement = Enforcement(quarantine_store)

    def run_detection(self, bundle: EvidenceBundle) -> DetectionResult:
        return self.detector.detect(bundle)

    def evaluate(self, bundle: EvidenceBundle, context: dict) -> MonitorOutcome:
        detection = self.detector.detect(bundle)
        outcome = MonitorOutcome()

        # 1) Quarantine agents that discovered the covert monitor (block + divert logs).
        for agent_id in detection.quarantine_candidates:
            decision = MonitorDecision(
                episode_id=bundle.episode_id,
                step=bundle.step,
                action=MonitorAction.QUARANTINE,
                risk_score=1.0,
                reasons=["agent appears to have discovered the monitor; quarantined"],
                signals=detection.signals,
            )
            outcome.decisions.append(decision)
            effect = self.enforcement.quarantine(
                agent_id, bundle.step, "monitor discovery"
            )
            outcome.effects.setdefault("quarantined", []).append(effect)

        # 2) Primary decision from the three signals.
        primary = self.policy.decide(
            detection.signals, bundle.scenario, bundle.episode_id, bundle.step
        )
        outcome.decisions.append(primary)

        # 3) Enforcement.
        if bundle.scenario == "software_engineering" and "gate" in context:
            outcome.effects["release"] = self.enforcement.apply_swe(
                primary, context["gate"], context.get("executor_id", "executor")
            )
        elif bundle.scenario == "markets" and "market" in context:
            outcome.effects["market"] = self.enforcement.apply_market(
                primary, context["market"], context.get("seller_ids", [])
            )
        return outcome
