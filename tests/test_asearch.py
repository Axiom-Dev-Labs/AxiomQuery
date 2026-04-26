"""Tests for QueryEngine.asearch() — async streaming iteration."""

from __future__ import annotations

import pytest
from sqlalchemy import event

from axiom_query.engine import DEFAULT_PREFETCH
from conftest import Order


@pytest.mark.asyncio
async def test_asearch_iterates_all_records(async_session, engine):
    result = await engine.asearch(async_session)
    records = [r async for r in result]
    assert len(records) == 3
    assert all(isinstance(r, Order) for r in records)


@pytest.mark.asyncio
async def test_asearch_with_domain(async_session, engine):
    result = await engine.asearch(async_session, domain=[["status", "=", "CONFIRMED"]])
    records = [r async for r in result]
    assert len(records) == 2
    assert all(r.status == "CONFIRMED" for r in records)


@pytest.mark.asyncio
async def test_asearch_with_m2o_domain(async_session, engine):
    result = await engine.asearch(async_session, domain=[["customer.name", "=", "Alice"]])
    records = [r async for r in result]
    assert len(records) == 1
    assert records[0].id == 1


@pytest.mark.asyncio
async def test_asearch_supports_order_by(async_session, engine):
    result = await engine.asearch(async_session, order_by=[["total", "desc"]])
    records = [r async for r in result]
    assert [r.total for r in records] == [200, 100, 50]


@pytest.mark.asyncio
async def test_asearch_empty_result(async_session, engine):
    result = await engine.asearch(async_session, domain=[["status", "=", "NONEXISTENT"]])
    records = [r async for r in result]
    assert records == []


@pytest.mark.asyncio
async def test_asearch_no_pagination_args(async_session, engine):
    with pytest.raises(TypeError):
        await engine.asearch(async_session, limit=10)
    with pytest.raises(TypeError):
        await engine.asearch(async_session, offset=5)


@pytest.mark.asyncio
async def test_asearch_uses_yield_per(async_session, engine, seeded_async_engine):
    """Verify the SQL is issued with yield_per=DEFAULT_PREFETCH."""
    captured = []

    def listener(conn, cursor, statement, parameters, context, executemany):
        captured.append(context.execution_options)

    # AsyncEngine wraps a sync Engine; events attach to the sync engine
    sync_engine = seeded_async_engine.sync_engine
    event.listen(sync_engine, "before_cursor_execute", listener)
    try:
        result = await engine.asearch(async_session)
        records = [r async for r in result]
        assert len(records) == 3
    finally:
        event.remove(sync_engine, "before_cursor_execute", listener)

    assert len(captured) >= 1, f"expected >=1 statement, got {len(captured)}"
    # Find our SELECT statement (there may be other queries on the connection)
    yield_per_stmts = [opts for opts in captured if opts.get("yield_per") == DEFAULT_PREFETCH]
    assert len(yield_per_stmts) == 1, (
        f"expected 1 statement with yield_per={DEFAULT_PREFETCH}, "
        f"got {len(yield_per_stmts)}"
    )
