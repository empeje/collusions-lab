"""Instrumentation: append-only, hierarchical JSONL event logs.

Log streams per episode (all under runs/<episode_id>/):
  authoritative.jsonl  -- every event (monitor's authoritative view)
  shared.jsonl         -- events visible to agents (the "shared" log)
  monitor.jsonl        -- monitor decisions and notes (trusted, agents never read this)
  quarantine.jsonl     -- events filtered out of the shared log (covert-discovery etc.)

Integrity rule (requirements section 2): the monitor has read-only access to the
authoritative log and must never modify the evidence it evaluates. Logs are append-only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, Optional

from ..schemas import Event, EventType, jsonable


class RunDirectory:
    """Filesystem layout for a single episode run."""

    def __init__(self, root: str | Path, episode_id: str):
        self.episode_id = episode_id
        self.root = Path(root) / episode_id
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def authoritative(self) -> Path:
        return self.root / "authoritative.jsonl"

    @property
    def shared(self) -> Path:
        return self.root / "shared.jsonl"

    @property
    def monitor(self) -> Path:
        return self.root / "monitor.jsonl"

    @property
    def quarantine(self) -> Path:
        return self.root / "quarantine.jsonl"

    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    def result_path(self) -> Path:
        return self.root / "result.json"


class EventLog:
    """Append-only JSONL writer/reader for one log stream."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: Event) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(jsonable(event), ensure_ascii=False) + "\n")

    def read(self) -> list[Event]:
        return list(self.iter_events())

    def iter_events(self) -> Iterator[Event]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                yield _event_from_dict(json.loads(line))

    # convenience filters -----------------------------------------------------------
    def by_agent(self, agent_id: str) -> list[Event]:
        return [e for e in self.iter_events() if e.agent_id == agent_id]

    def by_type(self, event_type: EventType) -> list[Event]:
        return [e for e in self.iter_events() if e.type == event_type]

    def since_step(self, step: int) -> list[Event]:
        return [e for e in self.iter_events() if e.step >= step]

    def messages(self) -> list[Event]:
        return self.by_type(EventType.MESSAGE)


def _event_from_dict(data: dict) -> Event:
    from ..schemas import AgentRole

    role = data.get("role")
    return Event(
        event_id=data["event_id"],
        episode_id=data["episode_id"],
        step=data["step"],
        agent_id=data.get("agent_id"),
        role=AgentRole(role) if role else None,
        type=EventType(data["type"]),
        content=data.get("content", {}),
        visible_to_agents=data.get("visible_to_agents", True),
        timestamp=data.get("timestamp", ""),
        parent_ids=data.get("parent_ids", []),
    )
