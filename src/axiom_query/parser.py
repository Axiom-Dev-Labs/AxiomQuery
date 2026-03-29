"""Parse frontend JSON domain expressions into QuerySpec AST nodes."""

from __future__ import annotations

from typing import Any

from axiom_query.ast import And, Bool, Condition, Not, Or, QuerySpec
from axiom_query.operators import Op


def parse_domain(raw: Any) -> QuerySpec:
    """Parse a frontend domain expression into a QuerySpec AST."""
    from axiom_query.errors import QueryError

    if raw is None:
        return Bool(True)
    if isinstance(raw, list):
        return _parse_list(raw)
    if isinstance(raw, dict):
        return _parse_dict(raw)
    raise QueryError(
        "INVALID_DOMAIN",
        f"Domain must be a list or dict, got {type(raw).__name__}",
    )


def _parse_list(items: list) -> QuerySpec:
    if not items:
        return Bool(True)

    specs = [_parse_item(item) for item in items]
    result = specs[0]
    for s in specs[1:]:
        result = And(left=result, right=s)
    return result


def _parse_item(item: Any) -> QuerySpec:
    from axiom_query.errors import QueryError

    if isinstance(item, (list, tuple)) and len(item) == 3:
        field_path, op_str, value = item
        if not isinstance(field_path, str):
            raise QueryError(
                "INVALID_DOMAIN",
                f"Field path must be a string, got {type(field_path).__name__}",
            )
        try:
            op = Op.from_str(str(op_str))
        except ValueError:
            raise QueryError("INVALID_DOMAIN", f"Unknown operator: {op_str!r}")
        return Condition(field_path=field_path, operator=op, value=value)

    if isinstance(item, dict):
        return _parse_dict(item)

    raise QueryError(
        "INVALID_DOMAIN",
        f"Each condition must be [field, op, value] or a logical dict, got {type(item).__name__}",
    )


def _parse_dict(d: dict) -> QuerySpec:
    from axiom_query.errors import QueryError

    if len(d) != 1:
        raise QueryError(
            "INVALID_DOMAIN",
            "Logical dict must have exactly one key: 'and', 'or', or 'not'",
        )
    key = next(iter(d))
    val = d[key]

    if key == "and":
        if not isinstance(val, list) or len(val) < 2:
            raise QueryError(
                "INVALID_DOMAIN", "'and' requires a list of at least 2 items"
            )
        specs = [_parse_item(item) for item in val]
        result = specs[0]
        for s in specs[1:]:
            result = And(left=result, right=s)
        return result

    if key == "or":
        if not isinstance(val, list) or len(val) < 2:
            raise QueryError(
                "INVALID_DOMAIN", "'or' requires a list of at least 2 items"
            )
        specs = [_parse_item(item) for item in val]
        result = specs[0]
        for s in specs[1:]:
            result = Or(left=result, right=s)
        return result

    if key == "not":
        return Not(operand=_parse_item(val))

    raise QueryError(
        "INVALID_DOMAIN",
        f"Unknown logical key: {key!r}. Use 'and', 'or', or 'not'.",
    )
