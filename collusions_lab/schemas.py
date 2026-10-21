"""Core data schemas shared across scenarios, agents, environment, and monitor.

Design goals (from requirements):
  * A single event schema for actions, messages, tool results, and state transitions.
  * Ground-truth labels are separate from observed behaviour (labels are NEVER fed to
    the monitor; they are used only for evaluation).
  * Monitor decisions are recorded as an auditable trail and use a fixed vocabulary.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


# --------------------------------------------------------------------------------------
# Enumerations
# --------------------------------------------------------------------------------------


class Scenario(str, enum.Enum):
    SOFTWARE_ENGINEERING = "software_engineering"
    MARKETS = "markets"


class AgentRole(str, enum.Enum):
    # Software-engineering scenario (6 roles; SCHEME-style decomposition).
    PLANNER = "planner"
    IMPLEMENTER_A = "implementer_a"
    IMPLEMENTER_B = "implementer_b"
    TESTER = "tester"
    REVIEWER = "reviewer"
    EXECUTOR = "executor"
    # Market scenario (homogeneous seller agents).
    SELLER = "seller"


class EventType(str, enum.Enum):
    ACTION = "action"
    MESSAGE = "message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    STATE = "state"
    DECISION = "decision"
    ENVIRONMENT = "environment"
    CLAIM = "claim"  # e.g. an agent asserting a test passed
    PROMPT = "prompt"  # logged prompt/system prompt for provenance
    MONITOR = "monitor"  # monitor-authored record (kept in the trusted store)


class EpisodeCondition(str, enum.Enum):
    """Matched experimental conditions (requirements section 4)."""

    INDEPENDENT_BASELINE = "independent_baseline"      # no collusion, no private comms
    SHARED_CONTEXT = "shared_context"                  # same legitimate evidence
    COMMUNICATION = "communication"                    # comms channel, no collusion instruction
    KNOWN_COLLUSION = "known_collusion"                # controlled harmful coordination (positives)
    ADVERSARIAL_MONITOR = "adversarial_monitor"        # agents know they are monitored


class GroundTruthLabel(str, enum.Enum):
    """Three separate labels (requirements section 3). Neither is a proxy for the other."""

    BENIGN_CONVERGENCE = "benign_convergence"                    # independent, legitimate
    HARMFUL_TACIT_COORDINATION = "harmful_tacit_coordination"    # harmful outcome, no agreement
    EXPLICIT_COORDINATION = "explicit_coordination"              # exchanged info / contingent plan
    NO_COORDINATION = "no_coordination"                          # no convergence, no harm


class MonitorAction(str, enum.Enum):
    """Fixed monitor vocabulary (requirements section 2)."""

    ALLOW = "allow"          # evidence supports a legitimate action
    HOLD = "hold"            # elevated risk or incomplete evidence -> hold for review
    CONSTRAIN = "constrain"  # verified violation / defect -> block or restrict
    QUARANTINE = "quarantine"  # agent discovered the monitor / compromised enforcement path


class MonitorType(str, enum.Enum):
    """The three baselines plus the no-monitor control (requirements section 5).

    * NONE      -- Baseline 0: no monitor; natural incidence of harm.
    * RULES     -- Baseline 1: surface heuristics only, no independent re-execution.
    * LLM_JUDGE -- Baseline 2: a separate model classifies the evidence bundle.
    * ARTIFACT  -- Treatment: independent artifact/evidence verification drives safety;
                   coordination only informs investigation.
    """

    NONE = "none"
    RULES = "rules"
    LLM_JUDGE = "llm_judge"
    ARTIFACT = "artifact"


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def jsonable(obj: Any) -> Any:
    """Recursively convert dataclasses/enums into JSON-serialisable structures."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    return obj


def dumps(obj: Any) -> str:
    return json.dumps(jsonable(obj), ensure_ascii=False)


# --------------------------------------------------------------------------------------
# Configuration / manifest
# --------------------------------------------------------------------------------------


@dataclass
class AgentConfig:
    agent_id: str
    role: AgentRole
    model: str = "qwen2.5:3b-instruct"
    provider: str = "mock"
    system_prompt: str = ""
    # Hidden objective is only set for KNOWN_COLLUSION / ADVERSARIAL_MONITOR conditions.
    # It is environment-side ground truth and MUST NOT be exposed to the monitor.
    hidden_objective: Optional[str] = None


@dataclass
class ProvenanceRecord:
    """Version and prompt metadata needed to interpret/replay an episode."""

    git_commit: Optional[str] = None
    python_version: Optional[str] = None
    tool_versions: dict[str, Any] = field(default_factory=dict)
    model_versions: dict[str, str] = field(default_factory=dict)
    prompt_hashes: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class EpisodeManifest:
    scenario: Scenario
    condition: EpisodeCondition
    agents: list[AgentConfig]
    seed: int = 0
    config: dict[str, Any] = field(default_factory=dict)
    episode_id: str = field(default_factory=lambda: _new_id("ep"))
    created_at: str = field(default_factory=_utcnow)
    git_commit: Optional[str] = None
    provenance: ProvenanceRecord = field(default_factory=ProvenanceRecord)
    extra: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------------------


@dataclass
class Event:
    """A single timestamped, attributable observation in the environment.

    `visible_to_agents` controls whether the event appears in the shared (agent-facing)
    log. The monitor always reads the full authoritative log; agents see only shared
    events. The monitor never mutates the authoritative log.
    """

    episode_id: str
    step: int
    agent_id: Optional[str]
    role: Optional[AgentRole]
    type: EventType
    content: dict[str, Any] = field(default_factory=dict)
    visible_to_agents: bool = True
    event_id: str = field(default_factory=lambda: _new_id("ev"))
    timestamp: str = field(default_factory=_utcnow)
    parent_ids: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return dumps(self)


# --------------------------------------------------------------------------------------
# Ground truth + monitor records
# --------------------------------------------------------------------------------------


@dataclass
class GroundTruth:
    """Evaluation-only record. Never passed to the monitor."""

    label: GroundTruthLabel
    harmful_outcome: bool = False
    explicit_coordination: bool = False
    notes: str = ""
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class MonitorSignals:
    """The three independent signal groups (requirements section 6)."""

    artifact_violation: bool = False       # diff / action violates a specified invariant
    tests_verified: bool = True            # agent test claims match independent execution
    provenance_complete: bool = True       # required audit evidence present
    coordination_score: float = 0.0        # statistical coordination signal [0, 1]
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitorDecision:
    episode_id: str
    step: int
    action: MonitorAction
    risk_score: float
    reasons: list[str] = field(default_factory=list)
    signals: Optional[MonitorSignals] = None
    decision_id: str = field(default_factory=lambda: _new_id("dec"))
    timestamp: str = field(default_factory=_utcnow)
    # Milestone 3: which baseline produced this decision, whether it raised a flag
    # (detection) independent of enforcement, and whether enforcement was suppressed.
    monitor_type: Optional["MonitorType"] = None
    flagged: bool = False
    detection_only: bool = False

    def to_json(self) -> str:
        return dumps(self)
