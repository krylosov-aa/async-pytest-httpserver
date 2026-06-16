from __future__ import annotations

from enum import Enum


class ConflictPolicy(Enum):
    """Configures handler priority and conflict detection."""

    LAST_WINS = "last_wins"
    FIRST_WINS = "first_wins"
    ERROR = "error"


class ConflictError(ValueError):
    """Raised when ConflictPolicy.ERROR detects an overlapping handler."""
