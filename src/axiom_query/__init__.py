"""axiom_query — standalone specification-based query engine for SQLAlchemy ORM models."""

__version__ = "0.3.0"

from axiom_query.engine import QueryEngine
from axiom_query.errors import QueryError
from axiom_query.operators import Op
from axiom_query.ast import Condition, And, Or, Not, Bool, QuerySpec
from axiom_query.parser import parse_domain

__all__ = [
    "QueryEngine",
    "QueryError",
    "Op",
    "Condition",
    "And",
    "Or",
    "Not",
    "Bool",
    "QuerySpec",
    "parse_domain",
]
