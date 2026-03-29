"""Compile a ReadGroupQuery AST into a SQLAlchemy SELECT ... GROUP BY ... HAVING statement."""

from __future__ import annotations

from datetime import date as pydate, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Date as SADate, func, select
from sqlalchemy.sql.expression import ColumnElement, Select

from axiom_query.aggregation import (
    AggFunc,
    AggregateSpec,
    DateGranularity,
    GroupBySpec,
    Pagination,
    ReadGroupQuery,
)
from axiom_query.compiler import _walk_ast, _make_alias_resolver
from axiom_query.schema import ModelSchema


def compile_read_group(
    query: ReadGroupQuery,
    schema: ModelSchema,
    pagination: Pagination | None = None,
    dialect_name: str = "default",
) -> Select:
    """Compile a ReadGroupQuery into a SQLAlchemy SELECT statement."""
    from axiom_query.errors import QueryError

    # Multi-child guard
    child_entities = query.referenced_child_entities
    if len(child_entities) > 1:
        raise QueryError(
            "MULTI_CHILD_AGGREGATION",
            f"Aggregating across multiple child entities simultaneously is not supported "
            f"(referenced: {', '.join(sorted(child_entities))}). "
            f"Aggregate one child entity at a time.",
        )

    # Build JOINs for child entities
    from_clause = schema.table
    joined_children: dict[str, Any] = {}

    for child_name in child_entities:
        child = schema.children.get(child_name)
        if child is None:
            raise QueryError(
                "INVALID_FILTER_FIELD",
                f"No child relation '{child_name}' on {schema.model_class.__name__}",
            )
        joined_children[child_name] = child
        from_clause = from_clause.outerjoin(
            child.table,
            schema.table.c.id == child.table.c[child.fk_field],
        )

    # Build SELECT columns
    select_columns = []
    groupby_exprs: dict[str, ColumnElement] = {}

    for g in query.groupby:
        expr = _compile_groupby_column(g, schema, joined_children, dialect_name)
        groupby_exprs[g.alias] = expr
        select_columns.append(expr.label(g.alias))

    aggregate_exprs: dict[str, ColumnElement] = {}
    for a in query.aggregates:
        expr = _compile_aggregate_column(a, schema, joined_children)
        aggregate_exprs[a.alias] = expr
        select_columns.append(expr.label(a.alias))

    if not select_columns:
        raise QueryError(
            "INVALID_READ_GROUP",
            "read_group must have at least one groupby or aggregate expression",
        )

    stmt = select(*select_columns).select_from(from_clause)

    # WHERE
    if query.domain is not None:
        from axiom_query.compiler import compile_domain
        where_clause = compile_domain(query.domain, schema)
        stmt = stmt.where(where_clause)

    # GROUP BY
    if groupby_exprs:
        stmt = stmt.group_by(*groupby_exprs.values())

    # HAVING
    if query.having is not None:
        alias_map = {**groupby_exprs, **aggregate_exprs}
        resolver = _make_alias_resolver(alias_map)
        having_clause = _walk_ast(query.having, resolver)
        stmt = stmt.having(having_clause)

    # ORDER BY / LIMIT / OFFSET
    if pagination is not None:
        if pagination.order_by:
            alias_map_all = {**groupby_exprs, **aggregate_exprs}
            order_clauses = _compile_order_by(pagination.order_by, alias_map_all)
            stmt = stmt.order_by(*order_clauses)

        if pagination.limit is not None:
            stmt = stmt.limit(pagination.limit)
        if pagination.offset is not None:
            stmt = stmt.offset(pagination.offset)

    return stmt


def _date_trunc_expr(granularity: DateGranularity, col: ColumnElement, dialect_name: str) -> ColumnElement:
    """Return dialect-appropriate date truncation expression."""
    if dialect_name == "sqlite":
        fmt_map = {
            DateGranularity.DAY: "%Y-%m-%d",
            DateGranularity.WEEK: "%Y-%W",
            DateGranularity.MONTH: "%m",
            DateGranularity.QUARTER: "%m",  # approximate
            DateGranularity.YEAR: "%Y",
        }
        fmt = fmt_map[granularity]
        return func.strftime(fmt, col)
    else:
        return func.date_trunc(granularity.value, col).cast(SADate)


def _compile_groupby_column(
    spec: GroupBySpec,
    schema: ModelSchema,
    joined_children: dict,
    dialect_name: str,
) -> ColumnElement:
    col = _resolve_agg_column(spec.field_path, schema, joined_children)

    if spec.granularity is None:
        return col

    # Validate date field
    _validate_date_col(spec.field_path, col)
    return _date_trunc_expr(spec.granularity, col, dialect_name)


def _compile_aggregate_column(
    spec: AggregateSpec,
    schema: ModelSchema,
    joined_children: dict,
) -> ColumnElement:
    from axiom_query.errors import QueryError

    if spec.field_path is None:
        if spec.function != AggFunc.COUNT:
            raise QueryError(
                "INVALID_AGGREGATION",
                f"Only COUNT is valid without a field path, got {spec.function.value}",
            )
        return func.count()

    col = _resolve_agg_column(spec.field_path, schema, joined_children)

    if spec.function in (AggFunc.SUM, AggFunc.AVG):
        _validate_numeric_col(spec.field_path, col)

    match spec.function:
        case AggFunc.COUNT:
            return func.count(col)
        case AggFunc.SUM:
            return func.sum(col)
        case AggFunc.AVG:
            return func.avg(col)
        case AggFunc.MIN:
            return func.min(col)
        case AggFunc.MAX:
            return func.max(col)
        case _:
            from axiom_query.errors import QueryError
            raise QueryError(
                "INVALID_AGGREGATION",
                f"Unsupported aggregate function: {spec.function.value}",
            )


def _resolve_agg_column(
    field_path: str,
    schema: ModelSchema,
    joined_children: dict,
) -> ColumnElement:
    from axiom_query.errors import QueryError

    if "." in field_path:
        child_name, field_name = field_path.split(".", 1)
        child = joined_children.get(child_name) or schema.children.get(child_name)
        if child is None:
            raise QueryError(
                "INVALID_FILTER_FIELD",
                f"No child relation '{child_name}' on {schema.model_class.__name__}",
            )
        return child.table.c[field_name]
    else:
        if field_path not in schema.columns:
            raise QueryError(
                "INVALID_FILTER_FIELD",
                f"No field '{field_path}' on {schema.model_class.__name__}",
            )
        return schema.table.c[field_path]


def _validate_numeric_col(field_path: str, col: ColumnElement) -> None:
    """Validate that a column is numeric (for SUM/AVG)."""
    from axiom_query.errors import QueryError

    col_type = getattr(col, "type", None)
    if col_type is None:
        return
    try:
        py_type = col_type.python_type
        if not issubclass(py_type, (int, float, Decimal)):
            raise QueryError(
                "INVALID_AGGREGATION",
                f"SUM/AVG requires a numeric field. '{field_path}' is not numeric.",
            )
    except NotImplementedError:
        pass  # Can't determine, allow it


def _validate_date_col(field_path: str, col: ColumnElement) -> None:
    """Validate that a column is date/datetime (for date granularity)."""
    from axiom_query.errors import QueryError
    from sqlalchemy import Date, DateTime

    col_type = getattr(col, "type", None)
    if col_type is None:
        return
    if not isinstance(col_type, (Date, DateTime)):
        raise QueryError(
            "INVALID_AGGREGATION",
            f"Date granularity requires a date/datetime field. '{field_path}' is not a date type.",
        )


def _compile_order_by(
    order_by: list[tuple[str, str]],
    alias_map: dict[str, ColumnElement],
) -> list[ColumnElement]:
    from axiom_query.errors import QueryError

    result = []
    for alias, direction in order_by:
        expr = alias_map.get(alias)
        if expr is None:
            available = ", ".join(sorted(alias_map.keys()))
            raise QueryError(
                "INVALID_ORDER_BY",
                f"ORDER BY alias '{alias}' is not a groupby or aggregate alias. "
                f"Available: {available}",
            )
        if direction == "desc":
            result.append(expr.desc())
        else:
            result.append(expr.asc())
    return result


def build_group_domain(
    group_row: dict[str, Any],
    groupby_specs: list[GroupBySpec],
    original_domain: Any | None,
) -> list[Any]:
    """Build a domain expression that filters to the records in a specific group."""
    conditions: list[Any] = []

    for spec in groupby_specs:
        value = group_row.get(spec.alias)
        if value is None:
            conditions.append([spec.field_path, "is_null", True])
        elif spec.granularity is not None:
            start, end = _date_range_bounds(value, spec.granularity)
            conditions.append([spec.field_path, ">=", start])
            conditions.append([spec.field_path, "<", end])
        else:
            conditions.append([spec.field_path, "=", value])

    if original_domain is not None:
        if isinstance(original_domain, list):
            conditions.extend(original_domain)
        else:
            conditions.append(original_domain)

    return conditions


def _date_range_bounds(truncated_value: Any, granularity: DateGranularity) -> tuple[str, str]:
    """Compute [start, end) ISO bounds for a date-truncated group value."""
    dt: datetime | None = None

    if isinstance(truncated_value, datetime):
        dt = truncated_value.replace(tzinfo=None)
    elif isinstance(truncated_value, pydate):
        dt = datetime(truncated_value.year, truncated_value.month, truncated_value.day)
    elif isinstance(truncated_value, str):
        s = truncated_value.strip()
        clean = s.replace("T", " ")
        if "+" in clean:
            clean = clean[: clean.rindex("+")]
        elif clean.endswith("Z"):
            clean = clean[:-1]
        clean = clean.strip()

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m", "%Y"):
            try:
                dt = datetime.strptime(clean, fmt)
                break
            except ValueError:
                continue

        if dt is None and "-Q" in s:
            try:
                parts = s.split("-Q")
                year = int(parts[0])
                quarter = int(parts[1])
                dt = datetime(year, (quarter - 1) * 3 + 1, 1)
            except (ValueError, IndexError):
                pass

    if dt is None:
        return (str(truncated_value), str(truncated_value))

    match granularity:
        case DateGranularity.DAY:
            start = dt
            end = dt + timedelta(days=1)
        case DateGranularity.WEEK:
            start = dt
            end = dt + timedelta(weeks=1)
        case DateGranularity.MONTH:
            start = dt.replace(day=1)
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1, day=1)
            else:
                end = start.replace(month=start.month + 1, day=1)
        case DateGranularity.QUARTER:
            start = dt.replace(day=1)
            next_quarter_month = start.month + 3
            if next_quarter_month > 12:
                end = start.replace(year=start.year + 1, month=next_quarter_month - 12, day=1)
            else:
                end = start.replace(month=next_quarter_month, day=1)
        case DateGranularity.YEAR:
            start = dt.replace(month=1, day=1)
            end = start.replace(year=start.year + 1, month=1, day=1)
        case _:
            start = dt
            end = dt + timedelta(days=1)

    return (start.date().isoformat(), end.date().isoformat())
