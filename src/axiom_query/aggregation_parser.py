"""Parse frontend JSON read_group requests into ReadGroupQuery AST nodes."""

from __future__ import annotations

from typing import Any

from axiom_query.aggregation import (
    AggFunc,
    AggregateSpec,
    DateGranularity,
    GroupBySpec,
    Pagination,
    ReadGroupQuery,
)


def parse_read_group(raw: dict[str, Any]) -> tuple[ReadGroupQuery, Pagination]:
    """Parse a JSON read_group request body into a (ReadGroupQuery, Pagination) tuple."""
    from axiom_query.errors import QueryError

    if not isinstance(raw, dict):
        raise QueryError(
            "INVALID_READ_GROUP",
            f"read_group body must be a dict, got {type(raw).__name__}",
        )

    raw_groupby = raw.get("groupby", [])
    if not isinstance(raw_groupby, list):
        raise QueryError("INVALID_READ_GROUP", "groupby must be a list of strings")
    groupby = [parse_groupby_spec(s) for s in raw_groupby]

    raw_aggregates = raw.get("aggregates", ["__count"])
    if not isinstance(raw_aggregates, list):
        raise QueryError("INVALID_READ_GROUP", "aggregates must be a list of strings")
    if not raw_aggregates:
        raise QueryError(
            "INVALID_READ_GROUP",
            "aggregates must contain at least one spec (e.g. '__count')",
        )
    aggregates = [parse_aggregate_spec(s) for s in raw_aggregates]

    domain = None
    raw_domain = raw.get("domain")
    if raw_domain is not None:
        from axiom_query.parser import parse_domain
        domain = parse_domain(raw_domain)

    having = None
    raw_having = raw.get("having")
    if raw_having is not None:
        from axiom_query.parser import parse_domain
        having = parse_domain(raw_having)

    order_by = None
    raw_order = raw.get("order_by")
    if raw_order is not None:
        if not isinstance(raw_order, list):
            raise QueryError(
                "INVALID_READ_GROUP",
                "order_by must be a list of [alias, direction] pairs",
            )
        order_by = _parse_order_by(raw_order)

    limit = raw.get("limit")
    if limit is not None and (not isinstance(limit, int) or limit < 0):
        raise QueryError("INVALID_READ_GROUP", "limit must be a non-negative integer")

    offset = raw.get("offset")
    if offset is not None and (not isinstance(offset, int) or offset < 0):
        raise QueryError("INVALID_READ_GROUP", "offset must be a non-negative integer")

    query = ReadGroupQuery(
        groupby=groupby,
        aggregates=aggregates,
        domain=domain,
        having=having,
    )

    pagination = Pagination(
        order_by=order_by,
        limit=limit,
        offset=offset,
    )

    return query, pagination


def parse_aggregate_spec(spec: str) -> AggregateSpec:
    """Parse a single aggregate spec string."""
    from axiom_query.errors import QueryError

    if not isinstance(spec, str) or not spec.strip():
        raise QueryError(
            "INVALID_AGGREGATION",
            f"Aggregate spec must be a non-empty string, got {spec!r}",
        )

    spec = spec.strip()

    if spec == "__count":
        return AggregateSpec(field_path=None, function=AggFunc.COUNT, alias="__count")

    if ":" not in spec:
        raise QueryError(
            "INVALID_AGGREGATION",
            f"Aggregate spec must be 'field:function' or '__count', got '{spec}'",
        )

    parts = spec.rsplit(":", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise QueryError(
            "INVALID_AGGREGATION",
            f"Invalid aggregate spec format: '{spec}'. Expected 'field:function'.",
        )

    field_path, func_str = parts

    try:
        func = AggFunc.from_str(func_str)
    except ValueError as e:
        raise QueryError("INVALID_AGGREGATION", str(e))

    alias = f"{field_path.replace('.', '__')}__{func.value}"

    return AggregateSpec(field_path=field_path, function=func, alias=alias)


def parse_groupby_spec(spec: str) -> GroupBySpec:
    """Parse a single groupby spec string."""
    from axiom_query.errors import QueryError

    if not isinstance(spec, str) or not spec.strip():
        raise QueryError(
            "INVALID_AGGREGATION",
            f"Groupby spec must be a non-empty string, got {spec!r}",
        )

    spec = spec.strip()

    if ":" not in spec:
        return GroupBySpec(field_path=spec)

    parts = spec.rsplit(":", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise QueryError(
            "INVALID_AGGREGATION",
            f"Invalid groupby spec format: '{spec}'. Expected 'field:granularity'.",
        )

    field_path, granularity_str = parts

    try:
        granularity = DateGranularity.from_str(granularity_str)
    except ValueError as e:
        raise QueryError("INVALID_AGGREGATION", str(e))

    return GroupBySpec(field_path=field_path, granularity=granularity)


def _parse_order_by(raw: list[Any]) -> list[tuple[str, str]]:
    from axiom_query.errors import QueryError

    result: list[tuple[str, str]] = []
    for item in raw:
        if isinstance(item, str):
            result.append((item, "asc"))
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            alias, direction = item
            if not isinstance(alias, str):
                raise QueryError(
                    "INVALID_READ_GROUP",
                    f"order_by alias must be a string, got {type(alias).__name__}",
                )
            direction = str(direction).lower()
            if direction not in ("asc", "desc"):
                raise QueryError(
                    "INVALID_READ_GROUP",
                    f"order_by direction must be 'asc' or 'desc', got '{direction}'",
                )
            result.append((alias, direction))
        else:
            raise QueryError(
                "INVALID_READ_GROUP",
                "order_by items must be 'alias' or ['alias', 'asc'|'desc']",
            )
    return result
