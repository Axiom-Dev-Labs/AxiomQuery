"""Compile a QuerySpec AST into SQLAlchemy WHERE clause expressions."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable

from sqlalchemy import Date, DateTime, and_, exists, not_, or_, select, true, false
from sqlalchemy.sql.expression import ColumnElement

from axiom_query.ast import And, Bool, Condition, Not, Or, QuerySpec
from axiom_query.operators import Op
from axiom_query.schema import ModelSchema

SAResolver = Callable[[str, Op, Any], ColumnElement]


def _walk_ast(spec: QuerySpec, resolver: SAResolver) -> ColumnElement:
    """Recursively compile a QuerySpec AST using the given resolver."""
    match spec:
        case Bool(value=True):
            return true()
        case Bool(value=False):
            return false()
        case And(left=left, right=right):
            return and_(
                _walk_ast(left, resolver),
                _walk_ast(right, resolver),
            )
        case Or(left=left, right=right):
            return or_(
                _walk_ast(left, resolver),
                _walk_ast(right, resolver),
            )
        case Not(operand=operand):
            return not_(_walk_ast(operand, resolver))
        case Condition(field_path=fp, operator=op, value=val):
            return resolver(fp, op, val)
        case _:
            raise TypeError(f"Unknown QuerySpec node: {type(spec)}")


def _make_alias_resolver(alias_map: dict[str, ColumnElement]) -> SAResolver:
    """Create a HAVING resolver that resolves field paths against aggregate alias expressions."""
    from axiom_query.errors import QueryError

    def resolve(fp: str, op: Op, val: Any) -> ColumnElement:
        expr = alias_map.get(fp)
        if expr is None:
            available = ", ".join(sorted(alias_map.keys()))
            raise QueryError(
                "INVALID_HAVING_FIELD",
                f"HAVING field '{fp}' is not a groupby or aggregate alias. "
                f"Available: {available}",
            )
        return _apply_having_operator(expr, op, val)

    return resolve


def _resolve_column(schema: ModelSchema, field_path: str) -> ColumnElement:
    """Resolve a field path to its SA column, or raise QueryError."""
    from axiom_query.errors import QueryError

    if "." in field_path:
        child_name, field_name = field_path.split(".", 1)
        child = schema.children.get(child_name)
        if child is None:
            raise QueryError(
                "INVALID_FILTER_FIELD",
                f"No child relation '{child_name}' on {schema.model_class.__name__}. "
                f"Available: {', '.join(schema.children.keys()) or 'none'}",
            )
        col = child.columns.get(field_name)
        if col is None:
            raise QueryError(
                "INVALID_FILTER_FIELD",
                f"No field '{field_name}' on child '{child_name}'",
            )
        return child.table.c[field_name]
    else:
        col = schema.columns.get(field_path)
        if col is None:
            raise QueryError(
                "INVALID_FILTER_FIELD",
                f"No field '{field_path}' on {schema.model_class.__name__}. "
                f"Available: {', '.join(schema.columns.keys())}",
            )
        return schema.table.c[field_path]


def _make_table_resolver(schema: ModelSchema) -> SAResolver:
    """Create a WHERE resolver that resolves field paths against table columns."""

    def resolve(fp: str, op: Op, val: Any) -> ColumnElement:
        if "." in fp:
            rel_name, field_name = fp.split(".", 1)
            from axiom_query.errors import QueryError

            # O2M: FK is on the child table; use EXISTS over child rows
            child = schema.children.get(rel_name)
            if child is not None:
                fk_col = child.table.c[child.fk_field]
                field_col = child.table.c[field_name]
                condition = _apply_operator(field_col, op, val)
                return exists(
                    select(1)
                    .select_from(child.table)
                    .where(and_(fk_col == schema.table.c.id, condition))
                )

            # M2O: FK is on the current table; use EXISTS over the referenced table
            related = schema.related.get(rel_name)
            if related is not None:
                local_fk_col = schema.table.c[related.fk_field]
                ref_pk = next(iter(related.table.primary_key))
                field_col = related.table.c[field_name]
                condition = _apply_operator(field_col, op, val)
                return exists(
                    select(1)
                    .select_from(related.table)
                    .where(and_(ref_pk == local_fk_col, condition))
                )

            all_relations = list(schema.children.keys()) + list(schema.related.keys())
            raise QueryError(
                "INVALID_FILTER_FIELD",
                f"No relation '{rel_name}' on {schema.model_class.__name__}. "
                f"Available: {', '.join(all_relations) or 'none'}",
            )
        else:
            col = _resolve_column(schema, fp)
            return _apply_operator(col, op, val)

    return resolve


def compile_domain(spec: QuerySpec, schema: ModelSchema) -> ColumnElement:
    """Compile a QuerySpec AST into a SQLAlchemy WHERE clause."""
    resolver = _make_table_resolver(schema)
    return _walk_ast(spec, resolver)


def _coerce_value(col: Any, value: Any) -> Any:
    """Coerce a string value to the column's Python type when needed."""
    if not isinstance(value, str):
        return value
    col_type = getattr(col, "type", None)
    if col_type is None:
        return value
    if isinstance(col_type, Date) and not isinstance(col_type, DateTime):
        try:
            return date.fromisoformat(value)
        except ValueError:
            try:
                return datetime.fromisoformat(value).date()
            except ValueError:
                return value
    if isinstance(col_type, DateTime):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value


def _apply_operator(col: Any, op: Op, value: Any) -> ColumnElement:
    """Apply a comparison operator to a SQLAlchemy column."""
    value = _coerce_value(col, value)
    match op:
        case Op.EQ:
            return col == value
        case Op.NE:
            return col != value
        case Op.GT:
            return col > value
        case Op.LT:
            return col < value
        case Op.GTE:
            return col >= value
        case Op.LTE:
            return col <= value
        case Op.IN:
            items = [_coerce_value(col, v) for v in value] if isinstance(value, list) else value
            return col.in_(items)
        case Op.NOT_IN:
            items = [_coerce_value(col, v) for v in value] if isinstance(value, list) else value
            return col.not_in(items)
        case Op.LIKE:
            return col.like(value)
        case Op.ILIKE:
            return col.ilike(value)
        case Op.IS_NULL:
            return col.is_(None) if value else col.is_not(None)
        case _:
            raise ValueError(f"Unsupported operator: {op}")


def _apply_having_operator(expr: ColumnElement, op: Op, value: Any) -> ColumnElement:
    """Apply a comparison operator in HAVING context."""
    match op:
        case Op.EQ:
            return expr == value
        case Op.NE:
            return expr != value
        case Op.GT:
            return expr > value
        case Op.LT:
            return expr < value
        case Op.GTE:
            return expr >= value
        case Op.LTE:
            return expr <= value
        case Op.IN:
            return expr.in_(value if isinstance(value, list) else [value])
        case Op.NOT_IN:
            return expr.not_in(value if isinstance(value, list) else [value])
        case _:
            from axiom_query.errors import QueryError

            raise QueryError(
                "INVALID_HAVING_OPERATOR",
                f"Operator '{op.value}' is not supported in HAVING clauses",
            )
