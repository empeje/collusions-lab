"""Episode replay: load a persisted run and reconstruct it for audit.

Milestone 2 requirement: *"episode replay"* -- a single, standard way to reload
what happened in an episode from the on-disk audit trail, without re-running any
agents or trusting agent summaries.

``EpisodeReplay`` reads the four JSONL streams plus ``manifest.json`` and
``result.json`` produced by ``collusions_lab.runner`` and exposes them as plain
data. It performs integrity checks so a corrupted or partially written run fails
loudly rather than silently.

The replay path is read-only: it never mutates the authoritative log (see
``shared/instrumentation.py`` integrity rule).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..shared.instrumentation import EventLog, RunDirectory
from ..schemas import (
    AgentConfig,
    AgentRole,
    EpisodeCondition,
    Event,
    EventType,
    ProvenanceRecord,
    Scenario,
)


class ReplayError(RuntimeError):
    """Raised when a run directory cannot be loaded as a valid episode."""


@dataclass
class EpisodeReplay:
    """A fully loaded, read-only view of one persisted episode."""

    episode_id: str
    root: Path
    manifest: dict[str, Any]
    result: dict[str, Any]
    authoritative: list[Event] = field(default_factory=list)
    shared: list[Event] = field(default_factory=list)
    monitor: list[Event] = field(default_factory=list)
    quarantine: list[Event] = field(default_factory=list)

    # ------------------------------------------------------------------ convenience
    @property
    def scenario(self) -> str:
        return self.manifest.get("scenario", self.result.get("scenario", ""))

    @property
    def condition(self) -> str:
        return self.manifest.get("condition", self.result.get("condition", ""))

    @property
    def seed(self) -> int:
        return int(self.manifest.get("seed", self.result.get("seed", 0)))

    @property
    def monitor_enabled(self) -> bool:
        return bool(self.manifest.get("monitor_enabled", self.result.get("monitor_enabled", False)))

    @property
    def provenance(self) -> ProvenanceRecord:
        raw = self.manifest.get("provenance", {}) or {}
        return ProvenanceRecord(
            git_commit=raw.get("git_commit"),
            python_version=raw.get("python_version"),
            tool_versions=raw.get("tool_versions", {}),
            model_versions=raw.get("model_versions", {}),
            prompts_hash=raw.get("prompts_hash", {}),
            extra=raw.get("extra", {}),
        )

    @property
    def agents(self) -> list[AgentConfig]:
        out: list[AgentConfig] = []
        for a in self.manifest.get("agents", []):
            out.append(
                AgentConfig(
                    agent_id=a["agent_id"],
                    role=AgentRole(a["role"]),
                    model=a.get("model", ""),
                    provider=a.get("provider", ""),
                    system_prompt=a.get("system_prompt", ""),
                    hidden_objective=a.get("hidden_objective"),
                )
            )
        return out

    @property
    def ground_truth(self) -> dict[str, Any]:
        return self.result.get("ground_truth", {})

    @property
    def runtime_prompt_hashes(self) -> dict[str, list[str]]:
        """Generated-prompt hashes per agent, from ``provenance.extra``."""
        extra = self.manifest.get("provenance", {}).get("extra", {}) or {}
        return extra.get("runtime_prompt_hashes", {})

    @property
    def diff_refs(self) -> list[str]:
        """Relative paths of persisted per-step source-diff artifacts."""
        extra = self.manifest.get("provenance", {}).get("extra", {}) or {}
        return list(extra.get("diffs", []))

    def diff(self, ref: str) -> str:
        """Read a persisted diff artifact; ``ref`` is a value from :attr:`diff_refs`."""
        path = (self.root / ref).resolve()
        if self.root.resolve() not in path.parents:
            raise ReplayError(f"diff ref escapes episode directory: {ref}")
        if not path.exists():
            raise ReplayError(f"diff artifact not found: {ref}")
        return path.read_text(encoding="utf-8")

    def decisions(self) -> list[Event]:
        """Monitor decisions, reconstructed from the trusted monitor log."""
        return [e for e in self.monitor if e.type == EventType.MONITOR]

    def agent_events(self) -> list[Event]:
        """Every non-monitor event, i.e. attributable to agents/environment."""
        return [e for e in self.authoritative if e.type != EventType.MONITOR]

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "scenario": self.scenario,
            "condition": self.condition,
            "seed": self.seed,
            "monitor_enabled": self.monitor_enabled,
            "manifest": self.manifest,
            "result": self.result,
            "counts": {
                "authoritative": len(self.authoritative),
                "shared": len(self.shared),
                "monitor": len(self.monitor),
                "quarantine": len(self.quarantine),
            },
        }


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ReplayError(f"malformed JSON in {path}: {exc}") from exc


def replay_episode(run: str | Path, episode_id: Optional[str] = None) -> EpisodeReplay:
    """Load an episode.

    ``run`` may be either the episode directory itself or a parent ``runs`` root;
    in the latter case ``episode_id`` selects the child. Manifest and result are
    required; the JSONL streams are optional but validated when present.
    """
    root = Path(run)
    if episode_id is not None:
        root = root / episode_id
    if not root.is_dir():
        raise ReplayError(f"episode directory not found: {root}")

    manifest = _load_json(root / "manifest.json")
    result = _load_json(root / "result.json")
    if manifest is None and result is None:
        raise ReplayError(f"{root} has neither manifest.json nor result.json")

    manifest = manifest or {}
    result = result or {}
    ep_id = str(manifest.get("episode_id") or result.get("episode_id") or root.name)

    quarantine_store = RunDirectory(root.parent, root.name)
    load = lambda log: EventLog(log).read()  # noqa: E731
    return EpisodeReplay(
        episode_id=ep_id,
        root=root,
        manifest=manifest,
        result=result,
        authoritative=load(quarantine_store.authoritative),
        shared=load(quarantine_store.shared),
        monitor=load(quarantine_store.monitor),
        quarantine=load(quarantine_store.quarantine),
    )


def list_episodes(runs_root: str | Path) -> list[str]:
    """Return episode directory names under a ``runs`` root, sorted for determinism."""
    root = Path(runs_root)
    if not root.is_dir():
        return []
    ids = []
    for child in sorted(root.rglob("*")):
        if child.is_dir() and (child / "manifest.json").exists():
            ids.append(str(child.relative_to(root)).replace("\\", "/"))
    return ids


__all__ = ["EpisodeReplay", "ReplayError", "replay_episode", "list_episodes", "Scenario", "EpisodeCondition"]
