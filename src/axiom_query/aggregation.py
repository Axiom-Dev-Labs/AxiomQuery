"""Immutable AST nodes for read_group (GROUP BY + aggregation) queries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from axiom_query.ast import QuerySpec


class AggFunc(str, Enum):
    """Supported SQL aggregate functions."""

    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"

    @classmethod
    def from_str(cls, s: str) -> AggFunc:
        try:
            return cls(s.lower())
        except ValueError:
            valid = ", ".join(m.value for m in cls)
            raise ValueError(
                f"Unknown aggregate function '{s}'. Valid: {valid}"
            )


class DateGranularity(str, Enum):
    """Date truncation granularities for GROUP BY on date/datetime fields."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"

    @classmethod
    def from_str(cls, s: str) -> DateGranularity:
        try:
            return cls(s.lower())
        except ValueError:
            valid = ", ".join(m.value for m in cls)
            raise ValueError(
                f"Unknown date granularity '{s}'. Valid: {valid}"
            )


@dataclass(frozen=True)
class AggregateSpec:
    """One aggregate expression in the SELECT list."""

    field_path: str | None
    function: AggFunc
    alias: str


@dataclass(frozen=True)
class GroupBySpec:
    """One GROUP BY expression."""

    field_path: str
    granularity: DateGranularity | None = None

    @property
    def alias(self) -> str:
        base = self.field_path.replace(".", "__")
        if self.granularity is not None:
            return f"{base}__{self.granularity.value}"
        return base


@dataclass(frozen=True)
class Pagination:
    """Presentation concerns for grouped queries."""

    order_by: list[tuple[str, str]] | None = None
    limit: int | None = None
    offset: int | None = None


@dataclass(frozen=True)
class ReadGroupQuery:
    """Complete read_group query specification."""

    groupby: list[GroupBySpec]
    aggregates: list[AggregateSpec]
    domain: QuerySpec | None = None
    having: QuerySpec | None = None

    @property
    def alias_map(self) -> dict[str, AggregateSpec | GroupBySpec]:
        m: dict[str, AggregateSpec | GroupBySpec] = {}
        for g in self.groupby:
            m[g.alias] = g
        for a in self.aggregates:
            m[a.alias] = a
        return m

    @property
    def referenced_relation_paths(self) -> set[tuple[str, ...]]:
        """Distinct relation-path prefixes (everything but the leaf field) across
        all groupby + aggregate field paths. E.g. "lines.product.category"
        contributes the prefix ("lines", "product")."""
        paths: set[tuple[str, ...]] = set()
        for g in self.groupby:
            if "." in g.field_path:
                paths.add(tuple(g.field_path.split(".")[:-1]))
        for a in self.aggregates:
            if a.field_path and "." in a.field_path:
                paths.add(tuple(a.field_path.split(".")[:-1]))
        return paths
