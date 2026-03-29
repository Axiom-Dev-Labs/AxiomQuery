"""Tests for QueryEngine.read_group() — slices 6-10."""

from __future__ import annotations


# Slice 6 — read_group basic
def test_read_group_count_by_status(session, engine):
    groups, total = engine.read_group(session, groupby=["status"], aggregates=["__count"])
    assert total == 2  # 2 distinct groups
    confirmed = next(g for g in groups if g["status"] == "CONFIRMED")
    assert confirmed["__count"] == 2
    draft = next(g for g in groups if g["status"] == "DRAFT")
    assert draft["__count"] == 1


# Slice 7 — read_group with domain
def test_read_group_with_domain(session, engine):
    groups, total = engine.read_group(
        session,
        groupby=["status"],
        aggregates=["__count"],
        domain=[["status", "=", "CONFIRMED"]],
    )
    assert total == 1
    assert groups[0]["__count"] == 2


# Slice 8 — read_group date granularity
def test_read_group_by_month(session, engine):
    groups, total = engine.read_group(
        session,
        groupby=["created_at:month"],
        aggregates=["__count"],
    )
    assert total == 2  # Jan and Feb
    jan = next(g for g in groups if "01" in str(g["created_at__month"]))
    assert jan["__count"] == 2  # orders 1 and 3
    feb = next(g for g in groups if "02" in str(g["created_at__month"]))
    assert feb["__count"] == 1


# Slice 9 — read_group child aggregate (LEFT JOIN)
def test_read_group_child_sum(session, engine):
    groups, total = engine.read_group(
        session,
        groupby=["status"],
        aggregates=["lines.quantity:sum"],
    )
    confirmed = next(g for g in groups if g["status"] == "CONFIRMED")
    # order1 lines: qty 2+3=5, order2 lines: qty 1 → confirmed total = 6
    assert confirmed["lines__quantity__sum"] == 6


# Slice 10 — HAVING + __domain drill-down
def test_read_group_having(session, engine):
    groups, total = engine.read_group(
        session,
        groupby=["status"],
        aggregates=["__count"],
        having=[["__count", ">", 1]],
    )
    assert total == 1
    assert groups[0]["status"] == "CONFIRMED"
    assert groups[0]["__count"] == 2


def test_read_group_domain_drilldown(session, engine):
    groups, _ = engine.read_group(session, groupby=["status"], aggregates=["__count"])
    confirmed = next(g for g in groups if g["status"] == "CONFIRMED")
    # Use __domain to list the records in that group
    records = engine.list(session, domain=confirmed["__domain"])
    assert len(records) == 2
    assert all(r.status == "CONFIRMED" for r in records)
