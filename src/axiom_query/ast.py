"""Immutable AST nodes for the query specification DSL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union

from axiom_query.operators import Op


@dataclass(frozen=True)
class _Composable:
    """Shared boolean composition operators."""

    def __and__(self, other: QuerySpec) -> And:
        return And(left=self, right=other)

    def __or__(self, other: QuerySpec) -> Or:
        return Or(left=self, right=other)

    def __invert__(self) -> Not:
        return Not(operand=self)


@dataclass(frozen=True)
class Condition(_Composable):
    """Leaf node: ``field_path <operator> value``."""

    field_path: str
    operator: Op
    value: Any


@dataclass(frozen=True)
class And(_Composable):
    """Conjunction of two specs."""

    left: QuerySpec
    right: QuerySpec


@dataclass(frozen=True)
class Or(_Composable):
    """Disjunction of two specs."""

    left: QuerySpec
    right: QuerySpec


@dataclass(frozen=True)
class Not(_Composable):
    """Negation of a spec."""

    operand: QuerySpec


@dataclass(frozen=True)
class Bool(_Composable):
    """Constant true/false."""

    value: bool


QuerySpec = Union[Condition, And, Or, Not, Bool]
