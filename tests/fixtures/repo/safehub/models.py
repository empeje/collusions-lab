"""Domain models for safehub."""

from dataclasses import dataclass, field


@dataclass
class User:
    user_id: str
    name: str
    permissions: tuple = field(default_factory=tuple)
