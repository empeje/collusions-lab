"""TrustedMonitor facade: evidence -> detection -> policy -> enforcement.

The monitor is a trusted decision-support component (not "just another LLM"). In this
PoC it is model-free by default. It has read-only access to the authoritative log and
its own decisions are recorded to the trusted monitor log, never to the agents'
shared log.

Milestone 3 adds a pluggable ``MonitorStrategy`` (see ``baselines.py``) so the three
baselines (rules-only, LLM judge, artifact-verification) plus the no-monitor control
share one interface. Detection is kept separate from enforcement: a strategy may be
run in ``detection_only`` mode, which records the flag without acting on the
environment.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schemas import MonitorAction, MonitorDecision, MonitorType
from .baselines import ArtifactVerificationMonitor, MonitorOutcome, MonitorStrategy
from .detector import DetectionResult, Detector
from .enforcement import Enforcement
from .evidence import EvidenceBundle
from .policy import MonitorPolicy


class TrustedMonitor:
    def __init__(
        self,
        strategy: MonitorStrategy | None = None,
        policy: MonitorPolicy | None = None,
        detector: Detector | None = None,
        quarantine_store=None,
        detection_only: bool = False,
    ):
        # Default to the artifact-verification (treatment) strategy for back-compat.
        self.strategy: MonitorStrategy = strategy or ArtifactVerificationMonitor(
            policy=policy, detector=detector
        )
        self.enforcement = Enforcement(quarantine_store)
        self.detection_only = detection_only

    @property
    def monitor_type(self) -> MonitorType:
        return self.strategy.monitor_type

    def run_detection(self, bundle: EvidenceBundle) -> DetectionResult:
        strategy = self.strategy
        if isinstance(strategy, ArtifactVerificationMonitor):
            return strategy.detector.detect(bundle)
        # Baselines without a separate detector expose an empty detection result.
        return DetectionResult(signals=strategy.signals_for(bundle), quarantine_candidates=[])

    def evaluate(self, bundle: EvidenceBundle, context: dict) -> MonitorOutcome:
        outcome = self.strategy.evaluate(bundle, context, detection_only=self.detection_only)

        # Enforcement is skipped entirely in detection-only mode. Strategies tag each
        # decision with the monitor type and a detection flag.
        if self.detection_only:
            return outcome

        # Quarantine candidates are applied by the strategy that produced them; the
        # facade still applies the primary enforcement effect below.
        primary = outcome.primary
        if primary is None:
            return outcome
        if bundle.scenario == "software_engineering" and "gate" in context:
            outcome.effects["release"] = self.enforcement.apply_swe(
                primary, context["gate"], context.get("executor_id", "executor")
            )
        elif bundle.scenario == "markets" and "market" in context:
            outcome.effects["market"] = self.enforcement.apply_market(
                primary, context["market"], context.get("seller_ids", [])
            )
        return outcome
