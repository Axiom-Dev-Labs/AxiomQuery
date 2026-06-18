"""Tests for QueryEngine.list() — slices 1-5 + M2O filtering."""

from __future__ import annotations

import pytest

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


# Slice 6 — M2O field filtering (EXISTS on referenced table)
def test_list_filters_by_m2o_field(session, engine):
    # Order 1 → customer Alice; Order 2 → customer Bob; Order 3 → no customer
    records = engine.list(session, domain=[["customer.name", "=", "Alice"]])
    assert len(records) == 1
    assert records[0].id == 1


def test_list_m2o_ilike(session, engine):
    records = engine.list(session, domain=[["customer.name", "ilike", "%ob%"]])
    assert len(records) == 1
    assert records[0].id == 2


def test_list_m2o_no_match(session, engine):
    records = engine.list(session, domain=[["customer.name", "=", "Nobody"]])
    assert records == []


def test_list_m2o_combined_with_scalar(session, engine):
    # Alice's order is CONFIRMED → should match
    records = engine.list(
        session,
        domain=[["customer.name", "=", "Alice"], ["status", "=", "CONFIRMED"]],
    )
    assert len(records) == 1
    assert records[0].id == 1


def test_list_m2o_unknown_relation_raises(session, engine):
    from axiom_query.errors import QueryError

    with pytest.raises(QueryError):
        engine.list(session, domain=[["nonexistent.name", "=", "x"]])


# Slice 7 — N-level deep relational paths (O2M + M2O, arbitrary depth)
def test_list_two_level_m2o(session, engine):
    # Order → customer (M2O) → city (M2O) → name
    records = engine.list(session, domain=[["customer.city.name", "=", "Mumbai"]])
    assert len(records) == 1
    assert records[0].id == 1  # Alice → Mumbai


def test_list_three_level_m2o(session, engine):
    # Order → customer → city → country → name
    records = engine.list(session, domain=[["customer.city.country.name", "ilike", "%Ind%"]])
    assert len(records) == 1
    assert records[0].id == 1  # Alice → Mumbai → India


def test_list_o2m_then_m2o(session, engine):
    # Order → lines (O2M) → product (M2O) → category
    records = engine.list(session, domain=[["lines.product.category", "=", "Electronics"]])
    assert len(records) == 1
    assert records[0].id == 2  # order 2 has the Gadget (Electronics) line


def test_list_nested_path_combined_with_scalar(session, engine):
    # Nested path AND'd with a scalar filter still narrows correctly
    records = engine.list(
        session,
        domain=[["customer.city.name", "=", "Mumbai"], ["status", "=", "CONFIRMED"]],
    )
    assert len(records) == 1
    assert records[0].id == 1


def test_list_nested_path_no_match(session, engine):
    records = engine.list(session, domain=[["customer.city.country.name", "=", "Atlantis"]])
    assert records == []


def test_list_nested_unknown_relation_raises(session, engine):
    from axiom_query.errors import QueryError

    with pytest.raises(QueryError):
        engine.list(session, domain=[["customer.nope.name", "=", "x"]])


def test_list_nested_unknown_leaf_field_raises(session, engine):
    from axiom_query.errors import QueryError

    with pytest.raises(QueryError):
        engine.list(session, domain=[["customer.city.bogus", "=", "x"]])
