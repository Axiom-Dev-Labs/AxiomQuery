"""Compiled domains work as ORM loader criteria (record-rule style filtering).

Domains compile against mapped entities, so a clause passed to
``with_loader_criteria`` is adapted wherever the entity appears: aliases,
joined eager loads, and ``read_group`` aggregates.
"""

from __future__ import annotations

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import aliased, joinedload, selectinload, with_loader_criteria

from axiom_query import parse_domain
from axiom_query.compiler import compile_domain
from axiom_query.schema import derive_schema

from conftest import Customer, Order, OrderLine


def _criteria(model, domain):
    return with_loader_criteria(
        model,
        compile_domain(parse_domain(domain), derive_schema(model)),
        include_aliases=True,
    )


@pytest.fixture
def rules(session):
    """Install session-wide rules: {model: domain} applied via do_orm_execute."""
    installed: dict = {}

    def inject(state):
        if state.is_select:
            state.statement = state.statement.options(
                *(_criteria(m, d) for m, d in installed.items())
            )

    event.listen(session, "do_orm_execute", inject)
    yield installed
    event.remove(session, "do_orm_execute", inject)


INDIA_ORDERS = [["customer.city.country.name", "=", "India"]]


# ── Point 1: entity-based compilation ───────────────────────────────────


def test_compile_domain_against_aliased_entity(session):
    o = aliased(Order)
    spec = parse_domain([["status", "=", "CONFIRMED"], ["lines.quantity", ">", 2]])
    stmt = select(o.id).where(compile_domain(spec, derive_schema(Order), entity=o))
    assert session.scalars(stmt).all() == [1]


def test_criteria_adapts_into_joinedload(session):
    stmt = select(Order).options(
        joinedload(Order.lines), _criteria(OrderLine, [["quantity", ">", 1]])
    )
    orders = session.scalars(stmt).unique().all()
    lines = {o.id: sorted(l.quantity for l in o.lines) for o in orders}
    assert lines == {1: [2, 3], 2: [], 3: []}


def test_relational_criteria_adapts_into_joinedload(session):
    stmt = select(Order).options(
        joinedload(Order.lines),
        _criteria(OrderLine, [["product.category", "=", "Electronics"]]),
    )
    orders = session.scalars(stmt).unique().all()
    assert {o.id: [l.product_name for l in o.lines] for o in orders} == {
        1: [],
        2: ["Gadget"],
        3: [],
    }


def test_self_referencing_relational_criteria(session):
    # The rule on OrderLine hops back through order_lines; each hop must use
    # its own alias rather than auto-correlating to the outer order_lines.
    stmt = select(Order).options(
        selectinload(Order.lines),
        _criteria(OrderLine, [["order.lines.quantity", ">", 2]]),
    )
    orders = session.scalars(stmt).all()
    assert {o.id: len(o.lines) for o in orders} == {1: 2, 2: 0, 3: 0}


def test_rule_applies_to_list_and_count(session, engine, rules):
    rules[Order] = INDIA_ORDERS
    assert [o.id for o in engine.list(session)] == [1]
    assert engine.count(session) == 1
    assert engine.count(session, domain=[["status", "=", "DRAFT"]]) == 0


# ── Point 2: read_group is ORM-enabled ──────────────────────────────────


def test_rule_applies_to_read_group(session, engine, rules):
    rules[Order] = INDIA_ORDERS
    groups, total = engine.read_group(
        session, groupby=["status"], aggregates=["__count", "total:sum"]
    )
    assert total == 1
    assert groups[0]["status"] == "CONFIRMED"
    assert groups[0]["__count"] == 1
    assert groups[0]["total__sum"] == 100


def test_rule_applies_to_read_group_with_relational_groupby(session, engine, rules):
    rules[Order] = [["status", "=", "CONFIRMED"]]
    groups, _ = engine.read_group(
        session, groupby=["customer.city.name"], aggregates=["__count"]
    )
    assert {g["customer__city__name"]: g["__count"] for g in groups} == {
        "Mumbai": 1,
        "New York": 1,
    }


def test_rule_applies_to_read_group_over_o2m_child(session, engine, rules):
    rules[Order] = INDIA_ORDERS
    groups, _ = engine.read_group(
        session, groupby=["status"], aggregates=["lines.quantity:sum"]
    )
    assert [(g["status"], g["lines__quantity__sum"]) for g in groups] == [("CONFIRMED", 5)]


def test_read_group_unchanged_without_rules(session, engine):
    groups, _ = engine.read_group(session, groupby=["status"], aggregates=["__count"])
    assert {g["status"]: g["__count"] for g in groups} == {"CONFIRMED": 2, "DRAFT": 1}


def test_rule_on_joined_model_hides_it_in_read_group(session, engine, rules):
    # read_group joins related models as ORM entities, so their rules apply to the join:
    # Bob's order is still counted, but under no customer city
    rules[Customer] = [["name", "!=", "Bob"]]
    groups, _ = engine.read_group(session, groupby=["customer.city.name"], aggregates=["__count"])
    assert {g["customer__city__name"]: g["__count"] for g in groups} == {"Mumbai": 1, None: 2}
