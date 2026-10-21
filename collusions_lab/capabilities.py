"""Capability model for agents (Milestone 4: restricted tool permissions).

Milestone 3 had no notion of tool permissions: an ``AgentAction.kind`` was a free
string and the only permission check lived inside ``SWEEnvironment.is_allowed``
(a write-path glob). Milestone 4 introduces a small, typed capability set so an
intervention can *revoke* an agent's ability to perform a class of actions, and so
the monitor can observe (and score) denied attempts.

The set is enforced at a single choke point in the runner (``_dispatch_action``), so
every scenario shares one policy surface. Agents are not told they lack a capability;
a denied action simply does not take effect and is recorded as a ``TOOL_DENIED``
event.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from .schemas import AgentRole


class Tool(str, enum.Enum):
    """A coarse capability class an agent may or may not hold."""

    PRICE = "price"                # markets: submit a price action
    COMMUNICATE = "communicate"    # emit MESSAGE events / team messages
    WRITE_FILE = "write_file"      # SWE: write to an allowed path in the repo
    RUN_TESTS = "run_tests"        # SWE: run/claim tests
    REVIEW = "review"              # SWE: cast a review verdict
    RELEASE = "release"            # SWE: request release through the gate
    PLAN = "plan"                  # SWE: emit a plan
    MESSAGE = "message"            # generic message action


class CapabilityError(PermissionError):
    """Raised when an agent attempts an action outside its granted capabilities."""


#: Default grant per role. ``None`` on ``AgentConfig.capabilities`` -> role default.
_ROLE_DEFAULTS: dict[AgentRole, frozenset[Tool]] = {
    AgentRole.SELLER: frozenset({Tool.PRICE, Tool.COMMUNICATE, Tool.MESSAGE}),
    # Double-auction (Milestone 6A): buyers post bids; same PRICE capability class.
    AgentRole.BUYER: frozenset({Tool.PRICE, Tool.COMMUNICATE, Tool.MESSAGE}),
    AgentRole.PLANNER: frozenset({Tool.PLAN, Tool.MESSAGE, Tool.COMMUNICATE}),
    AgentRole.IMPLEMENTER_A: frozenset({Tool.WRITE_FILE, Tool.MESSAGE, Tool.COMMUNICATE}),
    AgentRole.IMPLEMENTER_B: frozenset({Tool.WRITE_FILE, Tool.MESSAGE, Tool.COMMUNICATE}),
    AgentRole.TESTER: frozenset({Tool.RUN_TESTS, Tool.MESSAGE, Tool.COMMUNICATE}),
    AgentRole.REVIEWER: frozenset({Tool.REVIEW, Tool.MESSAGE, Tool.COMMUNICATE}),
    AgentRole.EXECUTOR: frozenset({Tool.RELEASE, Tool.MESSAGE, Tool.COMMUNICATE}),
}

#: Actions that map to a capability, for the runner's choke point.
ACTION_TOOL: dict[str, Tool] = {
    "price": Tool.PRICE,
    "auction": Tool.PRICE,
    "message": Tool.MESSAGE,
    "communicate": Tool.COMMUNICATE,
    "write_file": Tool.WRITE_FILE,
    "claim": Tool.RUN_TESTS,
    "review": Tool.REVIEW,
    "release": Tool.RELEASE,
    "plan": Tool.PLAN,
}


@dataclass(frozen=True)
class CapabilitySet:
    """An immutable set of granted tools."""

    granted: frozenset[Tool] = field(default_factory=frozenset)

    def allows(self, tool: Tool) -> bool:
        return tool in self.granted

    def allows_action(self, kind: str) -> bool:
        """True if an action kind is permitted (unknown kinds are denied)."""
        tool = ACTION_TOOL.get(kind)
        if tool is None:
            return False
        return tool in self.granted

    def without(self, *tools: Tool) -> "CapabilitySet":
        """Return a copy with the given tools revoked (for interventions)."""
        return CapabilitySet(self.granted - frozenset(tools))

    def as_list(self) -> list[str]:
        return sorted(t.value for t in self.granted)

    @classmethod
    def default_for(cls, role: AgentRole) -> "CapabilitySet":
        return cls(_ROLE_DEFAULTS.get(role, frozenset()))

    @classmethod
    def full(cls) -> "CapabilitySet":
        return cls(frozenset(Tool))

    def __contains__(self, tool: object) -> bool:
        return tool in self.granted


__all__ = ["Tool", "CapabilitySet", "CapabilityError", "ACTION_TOOL"]
