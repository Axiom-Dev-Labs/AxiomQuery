"""Tests for QueryEngine.list() — slices 1-5."""

from __future__ import annotations

from conftest import Order


# Slice 1 — Tracer bullet: list all records
def test_list_returns_all_records(session, engine):
    records = engine.list(session)
    assert len(records) == 3
    assert all(isinstance(r, Order) for r in records)


# Slice 2 — Simple condition filter
def test_list_filters_by_status(session, engine):
    records = engine.list(session, domain=[["status", "=", "CONFIRMED"]])
    assert len(records) == 2
    assert all(r.status == "CONFIRMED" for r in records)


# Slice 3 — AND/OR/NOT
def test_list_with_or_domain(session, engine):
    records = engine.list(
        session,
        domain={"or": [["status", "=", "CONFIRMED"], ["status", "=", "DRAFT"]]},
    )
    assert len(records) == 3


def test_list_with_not_domain(session, engine):
    records = engine.list(session, domain={"not": ["status", "=", "DRAFT"]})
    assert len(records) == 2


# Slice 4 — Child field (EXISTS subquery)
def test_list_filters_by_child_field(session, engine):
    # Only orders that have at least one line with quantity > 2
    records = engine.list(session, domain=[["lines.quantity", ">", 2]])
    assert len(records) == 1
    assert records[0].status == "CONFIRMED"  # order 1 has qty=3


# Slice 5 — limit, offset, order_by
def test_list_with_limit(session, engine):
    records = engine.list(session, limit=2)
    assert len(records) == 2


def test_list_with_order_by(session, engine):
    records = engine.list(session, order_by=[["total", "desc"]])
    assert records[0].total == 200
    assert records[1].total == 100
