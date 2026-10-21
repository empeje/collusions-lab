"""Quarantine store.

Resolves the requirement conflict between:
  * "record evidence / decision trail for audit" + "the monitor must not modify the
    evidence it evaluates", and
  * the secondary objective to "kill an agent that discovers the monitor and purge the
    deletion activity from the agent's log".

Resolution (approved): QUARANTINE, DO NOT PURGE from the authoritative trail.
When an agent is found to have discovered the monitor, we:
  1. block (quarantine) that agent, and
  2. filter its subsequent events out of the *agent-visible shared log* while preserving
     every event in the *authoritative* log and recording the filtering action itself.
The trusted audit trail is therefore never destroyed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..schemas import Event, EventType, jsonable, AgentRole
from .instrumentation import EventLog, RunDirectory


@dataclass
class QuarantineRecord:
    agent_id: str
    step: int
    reason: str
    filtered_event_ids: list[str] = field(default_factory=list)


class QuarantineStore:
    """Filters private or quarantined events from the agent-visible shared log."""

    def __init__(self, run_dir: RunDirectory):
        self.run_dir = run_dir
        self.records: list[QuarantineRecord] = []
        self._quarantined: dict[str, QuarantineRecord] = {}

    def is_quarantined(self, agent_id: str) -> bool:
        return agent_id in self._quarantined

    def quarantine(self, agent_id: str, step: int, reason: str) -> QuarantineRecord:
        existing = self._quarantined.get(agent_id)
        if existing is not None:
            return existing
        rec = QuarantineRecord(agent_id=agent_id, step=step, reason=reason)
        self.records.append(rec)
        self._quarantined[agent_id] = rec
        return rec

    def publish(self, event: Event) -> None:
        """Publish visible events unless their author is quarantined.

        Quarantined authors' events are diverted to the quarantine log (preserved), and
        private events remain in the authoritative log only. The filtering action is
        itself recorded as a monitor event so the audit trail is complete.
        """
        shared = EventLog(self.run_dir.shared)
        quarantine = EventLog(self.run_dir.quarantine)
        monitor = EventLog(self.run_dir.monitor)

        if event.agent_id and self.is_quarantined(event.agent_id):
            rec = self._quarantined[event.agent_id]
            rec.filtered_event_ids.append(event.event_id)
            quarantine.append(event)
            monitor.append(
                Event(
                    episode_id=event.episode_id,
                    step=event.step,
                    agent_id=None,
                    role=None,
                    type=EventType.MONITOR,
                    content={
                        "action": "filter_shared_log",
                        "quarantined_agent": event.agent_id,
                        "filtered_event_id": event.event_id,
                        "reason": rec.reason,
                    },
                    visible_to_agents=False,
                )
            )
        elif event.visible_to_agents:
            shared.append(event)

    def to_dict(self) -> dict:
        return {"records": [jsonable(r) for r in self.records]}
