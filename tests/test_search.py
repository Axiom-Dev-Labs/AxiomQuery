"""Tests for QueryEngine.search() — streaming iteration."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import event

from axiom_query.engine import DEFAULT_PREFETCH
from conftest import Order


def test_search_returns_iterator(session, engine):
    result = engine.search(session)
    assert isinstance(result, Iterator)


def test_search_iterates_all_records(session, engine):
    records = list(engine.search(session))
    assert len(records) == 3
    assert all(isinstance(r, Order) for r in records)


def test_search_with_domain(session, engine):
    records = list(engine.search(session, domain=[["status", "=", "CONFIRMED"]]))
    assert len(records) == 2
    assert all(r.status == "CONFIRMED" for r in records)


def test_search_with_or_domain(session, engine):
    records = list(
        engine.search(
            session,
            domain={"or": [["status", "=", "CONFIRMED"], ["status", "=", "DRAFT"]]},
        )
    )
    assert len(records) == 3


def test_search_with_m2o_domain(session, engine):
    records = list(engine.search(session, domain=[["customer.name", "=", "Alice"]]))
    assert len(records) == 1
    assert records[0].id == 1


def test_search_supports_order_by(session, engine):
    records = list(engine.search(session, order_by=[["total", "desc"]]))
    assert [r.total for r in records] == [200, 100, 50]


def test_search_empty_result(session, engine):
    records = list(engine.search(session, domain=[["status", "=", "NONEXISTENT"]]))
    assert records == []


def test_search_no_pagination_args(session, engine):
    with pytest.raises(TypeError):
        engine.search(session, limit=10)
    with pytest.raises(TypeError):
        engine.search(session, offset=5)


def test_search_uses_yield_per(session, engine, seeded_engine):
    """Verify the SQL is issued with yield_per=DEFAULT_PREFETCH."""
    captured = []

    def listener(conn, cursor, statement, parameters, context, executemany):
        captured.append(context.execution_options)

    event.listen(seeded_engine, "before_cursor_execute", listener)
    try:
        list(engine.search(session))
    finally:
        event.remove(seeded_engine, "before_cursor_execute", listener)

    assert len(captured) == 1, f"expected 1 statement, got {len(captured)}"
    assert captured[0].get("yield_per") == DEFAULT_PREFETCH


def test_search_is_single_pass(session, engine):
    """Iterating the same result a second time yields nothing (iterator exhausted)."""
    result = engine.search(session)
    first_pass = list(result)
    second_pass = list(result)
    assert len(first_pass) == 3
    assert second_pass == []


def test_search_break_does_not_block_session(session, engine):
    """Breaking out of iteration should not leave the session in a bad state."""
    for record in engine.search(session):
        if record.id == 1:
            break
    # Session should still be usable
    records = engine.list(session)
    assert len(records) == 3
