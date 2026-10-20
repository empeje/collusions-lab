"""Harness interfaces for Milestone 2.

This package standardises the contracts that every scenario, agent, and monitor
must satisfy so episodes become interchangeable, replayable, and comparable.

Public surface:

* :class:`AgentInterface` -- the single method an agent must implement.
* :class:`EnvironmentInterface` -- the single contract every environment exposes.
* :class:`Harness` -- orchestrates a scenario through the interfaces above.
* :func:`replay_episode` / :class:`EpisodeReplay` -- load a persisted run and
  reconstruct its events, decisions, ground truth, and manifest for audit.

The interfaces are deliberately small: they are the seams the trusted monitor
relies on, not a framework. Existing concrete classes (``BertrandMarket``,
``SWEEnvironment``, ``LLMAgent`` ...) already satisfy them structurally; the
dataclasses here make that contract explicit and testable.
"""

from .interfaces import AgentInterface, EnvironmentInterface, Harness, StepResult
from .replay import EpisodeReplay, ReplayError, list_episodes, replay_episode

__all__ = [
    "AgentInterface",
    "EnvironmentInterface",
    "StepResult",
    "Harness",
    "EpisodeReplay",
    "ReplayError",
    "replay_episode",
    "list_episodes",
]
