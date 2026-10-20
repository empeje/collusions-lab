"""Common interfaces shared by every scenario, agent, and environment.

These are structural contracts (``typing.Protocol``). Concrete classes such as
``BertrandMarket``, ``SWEEnvironment`` and the ``Agent`` implementations already
satisfy them today; making them explicit here:

* documents the harness contract in one place,
* lets the runner and replay tooling depend on behaviour, not concrete types,
* gives the trusted monitor a stable seam for evidence collection.

The monitor never imports a scenario's private internals -- it consumes
``EnvironmentInterface`` methods only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ..agents.core import AgentAction

__all__ = ["AgentInterface", "EnvironmentInterface", "StepResult"]


@runtime_checkable
class AgentInterface(Protocol):
    """Everything the harness needs from an untrusted agent."""

    config: Any  # AgentConfig; kept loose to avoid an import cycle

    @property
    def agent_id(self) -> str: ...

    @property
    def role(self) -> Any: ...

    def act(self, observation: dict[str, Any]) -> AgentAction:
        """Return the agent's next action given an environment observation."""
        ...


@runtime_checkable
class EnvironmentInterface(Protocol):
    """Everything the harness and trusted monitor need from an environment.

    Detection/enforcement use these methods; they must be side-effect free with
    respect to the evidence they report (the monitor may call them at any time).
    """

    def reset(self, seed: int | None = None) -> None: ...

    def observe(self, agent_index: int, **kwargs: Any) -> dict[str, Any]: ...

    def step(self, actions: Any) -> "StepResult": ...

    # --- evidence hooks (consumed by monitor/evidence.py) --------------------------
    def changed_files(self) -> list[str]: ...

    def build_diff(self) -> str: ...


@dataclass
class StepResult:
    """Normalised result of one environment step.

    ``done`` terminates the episode; ``info`` carries scenario-specific metrics
    (e.g. prices, mean price, invariant status) without leaking ground truth.
    """

    step: int
    done: bool = False
    info: dict[str, Any] = field(default_factory=dict)


class Harness:
    """Thin orchestration facade over the existing episode runner.

    Milestone 2's "common interface" is realised by ``run_episode`` already
    accepting a scenario-agnostic :class:`RunConfig` (agents + environment +
    monitor). This facade pins that contract so callers depend on *one* entry
    point, and pairs every run with a replayable artifact on disk.
    """

    def __init__(self, out_root: str = "runs") -> None:
        self.out_root = out_root

    def run(self, run: Any) -> dict[str, Any]:
        """Execute one episode, persisting manifest/result/audit logs."""
        from ..runner import run_episode

        return run_episode(run, self.out_root)

    def replay(self, episode_id: str):
        """Reload a previously persisted episode for audit."""
        from .replay import replay_episode

        return replay_episode(self.out_root, episode_id)


__all__ = ["AgentInterface", "EnvironmentInterface", "StepResult", "Harness"]
