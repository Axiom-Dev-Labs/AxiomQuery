"""Query operators for the specification DSL."""

from __future__ import annotations

from enum import Enum


class Op(str, Enum):
    """Comparison operators supported in query specifications."""

    EQ = "="
    NE = "!="
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    IN = "in"
    NOT_IN = "not in"
    LIKE = "like"
    ILIKE = "ilike"
    IS_NULL = "is_null"

    @classmethod
    def from_str(cls, s: str) -> Op:
        """Parse an operator string. Case-insensitive."""
        normalized = s.strip().lower()
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(f"Unknown operator: {s!r}")
