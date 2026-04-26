"""QueryEngine — public facade for axiom_query."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from axiom_query.aggregation import Pagination, ReadGroupQuery
from axiom_query.aggregation_parser import parse_read_group
from axiom_query.compiler import compile_domain
from axiom_query.compiler_aggregate import build_group_domain, compile_read_group
from axiom_query.parser import parse_domain
from axiom_query.schema import ModelSchema, derive_schema


DEFAULT_PREFETCH = 1000


def _get_dialect_name(session) -> str:
    """Extract dialect name from a sync or async SQLAlchemy session."""
    # AsyncSession has a .bind attribute (AsyncEngine)
    bind = getattr(session, "bind", None)
    if bind is not None:
        dialect = getattr(bind, "dialect", None)
        if dialect is not None:
            return dialect.name
    # Sync session: try get_bind()
    try:
        bind = session.get_bind()
        return bind.dialect.name
    except Exception:
        pass
    return "default"


class QueryEngine:
    """Specification-based query engine for a SQLAlchemy ORM model.

    Usage::

        engine = QueryEngine(Order)

        # Materialised page
        page = engine.list(session, domain=[["status", "=", "CONFIRMED"]], limit=20)

        # Streaming iteration over every match (no len/indexing)
        for order in engine.search(session, domain=[["status", "=", "CONFIRMED"]]):
            process(order)

        groups, total = engine.read_group(session, groupby=["status"], aggregates=["__count"])
    """

    def __init__(self, model_class: type) -> None:
        self._model = model_class
        self._schema: ModelSchema = derive_schema(model_class)

    # ── Statement builder ────────────────────────────────────────────────

    def _build_stmt(self, domain, order_by, limit, offset):
        stmt = select(self._model)
        if domain is not None:
            spec = parse_domain(domain)
            stmt = stmt.where(compile_domain(spec, self._schema))
        if order_by is not None:
            stmt = self._apply_order_by(stmt, order_by)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        return stmt

    # ── Sync API ─────────────────────────────────────────────────────────

    def list(
        self,
        session: Session,
        domain: Any = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: list | None = None,
    ) -> list:
        """Return all records matching the optional domain filter as a list.

        Materialises the full result. Use ``search()`` for streaming over large
        result sets.
        """
        stmt = self._build_stmt(domain, order_by, limit, offset)
        return list(session.execute(stmt).scalars().all())

    def search(
        self,
        session: Session,
        domain: Any = None,
        order_by: list | None = None,
    ):
        """Stream records for batch processing.

        Returns an iterator yielding ORM instances from a server-side cursor,
        fetched in batches of ``DEFAULT_PREFETCH`` (1000) rows. Single-pass —
        iterate once and don't store the iterator for re-use.

        No ``limit`` / ``offset``: this method is for processing every matching
        row. Use ``list()`` if you need pagination, ``len()``, or indexing.

        Driver note: true streaming requires a database driver with server-side
        cursor support (psycopg2, asyncpg). SQLite degrades to client-side
        iteration but remains correct.
        """
        stmt = self._build_stmt(domain, order_by, limit=None, offset=None)
        streaming_stmt = stmt.execution_options(yield_per=DEFAULT_PREFETCH)
        return iter(session.scalars(streaming_stmt))

    def read_group(
        self,
        session: Session,
        groupby: list[str],
        aggregates: list[str],
        domain: Any = None,
        having: Any = None,
        order_by: list | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[dict], int]:
        """Return grouped aggregation results with __domain drill-down per group."""
        raw = {
            "groupby": groupby,
            "aggregates": aggregates,
        }
        if domain is not None:
            raw["domain"] = domain
        if having is not None:
            raw["having"] = having
        if order_by is not None:
            raw["order_by"] = order_by
        if limit is not None:
            raw["limit"] = limit
        if offset is not None:
            raw["offset"] = offset

        query, pagination = parse_read_group(raw)

        # Get dialect name
        dialect_name = _get_dialect_name(session)

        stmt = compile_read_group(query, self._schema, pagination, dialect_name)
        rows = session.execute(stmt).mappings().all()

        groups = []
        for row in rows:
            group = dict(row)
            group["__domain"] = build_group_domain(group, query.groupby, domain)
            groups.append(group)

        return groups, len(groups)

    # ── Async API ─────────────────────────────────────────────────────────

    async def alist(
        self,
        session,
        domain: Any = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: list | None = None,
    ) -> list:
        """Async variant of ``list()`` — returns a materialised list."""
        stmt = self._build_stmt(domain, order_by, limit, offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def asearch(
        self,
        session,
        domain: Any = None,
        order_by: list | None = None,
    ):
        """Async variant of ``search()`` — returns an async iterator.

        Consume with ``async for``::

            async for record in await engine.asearch(session, domain=...):
                process(record)

        Streams ORM instances in batches of ``DEFAULT_PREFETCH`` (1000) rows
        from a server-side cursor. Single-pass; no ``limit`` / ``offset``.

        Driver note: true streaming requires a server-side cursor capable
        driver (asyncpg). aiosqlite iterates correctly but without driver-level
        streaming.
        """
        stmt = self._build_stmt(domain, order_by, limit=None, offset=None)
        streaming_stmt = stmt.execution_options(yield_per=DEFAULT_PREFETCH)
        return await session.stream_scalars(streaming_stmt)

    async def aread_group(
        self,
        session,
        groupby: list[str],
        aggregates: list[str],
        domain: Any = None,
        having: Any = None,
        order_by: list | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[dict], int]:
        """Async variant of read_group()."""
        raw = {
            "groupby": groupby,
            "aggregates": aggregates,
        }
        if domain is not None:
            raw["domain"] = domain
        if having is not None:
            raw["having"] = having
        if order_by is not None:
            raw["order_by"] = order_by
        if limit is not None:
            raw["limit"] = limit
        if offset is not None:
            raw["offset"] = offset

        query, pagination = parse_read_group(raw)

        # Get dialect name from async session
        dialect_name = _get_dialect_name(session)

        stmt = compile_read_group(query, self._schema, pagination, dialect_name)
        rows = (await session.execute(stmt)).mappings().all()

        groups = []
        for row in rows:
            group = dict(row)
            group["__domain"] = build_group_domain(group, query.groupby, domain)
            groups.append(group)

        return groups, len(groups)

    def _apply_order_by(self, stmt, order_by: list):
        """Apply order_by to a select statement."""
        for item in order_by:
            if isinstance(item, str):
                field, direction = item, "asc"
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                field, direction = item[0], str(item[1]).lower()
            else:
                continue

            if field in self._schema.columns:
                col = self._schema.table.c[field]
                if direction == "desc":
                    stmt = stmt.order_by(col.desc())
                else:
                    stmt = stmt.order_by(col.asc())

        return stmt
