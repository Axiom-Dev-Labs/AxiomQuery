"""Query error types for axiom_query."""

from __future__ import annotations


class QueryError(Exception):
    """Raised when a query specification is invalid."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
