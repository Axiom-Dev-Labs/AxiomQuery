"""Compile a QuerySpec AST into SQLAlchemy WHERE clause expressions."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable

from sqlalchemy import Date, DateTime, and_, not_, or_, true, false
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import ColumnElement

from axiom_query.ast import And, Bool, Condition, Not, Or, QuerySpec
from axiom_query.operators import Op
from axiom_query.schema import ModelSchema, derive_schema

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


def column_on(target: Any, schema: ModelSchema, name: str) -> ColumnElement:
    """Return column ``name`` of ``schema`` as it appears on ``target``.

    ``target`` is a mapped class or an ``aliased()`` entity; the column is
    resolved via the mapped attribute so ORM adaptation (aliases, joined eager
    loads, ``with_loader_criteria``) can retarget it.
    """
    prop = sa_inspect(schema.model_class).get_property_by_column(schema.columns[name])
    return getattr(target, prop.key)


def _resolve_column(schema: ModelSchema, target: Any, field_name: str) -> ColumnElement:
    """Resolve a scalar field on ``target`` to its SA column, or raise QueryError."""
    from axiom_query.errors import QueryError

    if field_name not in schema.columns:
        raise QueryError(
            "INVALID_FILTER_FIELD",
            f"No field '{field_name}' on {schema.model_class.__name__}. "
            f"Available: {', '.join(schema.columns.keys())}",
        )
    return column_on(target, schema, field_name)


def _resolve_path_condition(
    schema: ModelSchema, target: Any, segments: list[str], op: Op, val: Any
) -> ColumnElement:
    """Resolve a (possibly multi-hop) relational path into a WHERE condition.

    The leaf segment is a scalar column; every preceding segment is an O2M or
    M2O relation, compiled with the relationship's own ``any()`` / ``has()``
    so the EXISTS uses its full join condition (including extra criteria such
    as a model-name column), not just the foreign key. Each hop targets a
    fresh ``aliased()`` entity, so it never auto-correlates against the same
    table in an outer query.
    """
    from axiom_query.errors import QueryError

    head, *rest = segments

    # Leaf: scalar column on the current model
    if not rest:
        return _apply_operator(_resolve_column(schema, target, head), op, val)

    # O2M: any child row matches
    child = schema.children.get(head)
    if child is not None:
        child_entity = aliased(child.model_class)
        inner = _resolve_path_condition(
            derive_schema(child.model_class), child_entity, rest, op, val
        )
        return getattr(target, head).of_type(child_entity).any(inner)

    # M2O: the referenced row matches
    related = schema.related.get(head)
    if related is not None:
        ref_entity = aliased(related.model_class)
        inner = _resolve_path_condition(
            derive_schema(related.model_class), ref_entity, rest, op, val
        )
        return getattr(target, head).of_type(ref_entity).has(inner)

    all_relations = list(schema.children.keys()) + list(schema.related.keys())
    raise QueryError(
        "INVALID_FILTER_FIELD",
        f"No relation '{head}' on {schema.model_class.__name__}. "
        f"Available: {', '.join(all_relations) or 'none'}",
    )


def _make_entity_resolver(schema: ModelSchema, entity: Any) -> SAResolver:
    """Create a WHERE resolver that resolves field paths against a mapped entity."""

    def resolve(fp: str, op: Op, val: Any) -> ColumnElement:
        return _resolve_path_condition(schema, entity, fp.split("."), op, val)

    return resolve


def compile_domain(
    spec: QuerySpec, schema: ModelSchema, entity: Any = None
) -> ColumnElement:
    """Compile a QuerySpec AST into a SQLAlchemy WHERE clause.

    Columns are resolved through ``entity``: the mapped class by default, or
    an ``aliased()`` entity to filter that alias. Because the clause is built
    from mapped attributes, SQLAlchemy can adapt it wherever the entity is
    aliased, e.g. when passed to ``with_loader_criteria`` and rendered inside a
    ``joinedload``.
    """
    resolver = _make_entity_resolver(
        schema, schema.model_class if entity is None else entity
    )
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
