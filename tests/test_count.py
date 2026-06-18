"""Tests for QueryEngine.count() and acount()."""

from __future__ import annotations

import pytest


# ── Sync count() ─────────────────────────────────────────────────────────


def test_count_no_domain(session, engine):
    assert engine.count(session) == 3
    assert engine.count(session) == len(engine.list(session))


def test_count_simple_condition(session, engine):
    domain = [["status", "=", "CONFIRMED"]]
    assert engine.count(session, domain=domain) == 2
    assert engine.count(session, domain=domain) == len(engine.list(session, domain=domain))


def test_count_and_or_not(session, engine):
    # status == DRAFT OR total > 150  → orders 2 (CONFIRMED/200) and 3 (DRAFT/50)
    or_domain = {"or": [["status", "=", "DRAFT"], ["total", ">", 150]]}
    assert engine.count(session, domain=or_domain) == 2
    assert engine.count(session, domain=or_domain) == len(engine.list(session, domain=or_domain))

    not_domain = {"not": ["status", "=", "DRAFT"]}
    assert engine.count(session, domain=not_domain) == 2


def test_count_o2m_child_path(session, engine):
    # Orders having a line with quantity > 2 → only order 1
    domain = [["lines.quantity", ">", 2]]
    assert engine.count(session, domain=domain) == 1
    assert engine.count(session, domain=domain) == len(engine.list(session, domain=domain))


def test_count_m2o_path(session, engine):
    domain = [["customer.name", "=", "Alice"]]
    assert engine.count(session, domain=domain) == 1
    assert engine.count(session, domain=domain) == len(engine.list(session, domain=domain))


def test_count_n_level_path(session, engine):
    # Order → customer → city → country.name
    domain = [["customer.city.country.name", "=", "India"]]
    assert engine.count(session, domain=domain) == 1
    assert engine.count(session, domain=domain) == len(engine.list(session, domain=domain))


# ── Async acount() ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_acount_no_domain(async_session, engine):
    assert await engine.acount(async_session) == 3


@pytest.mark.asyncio
async def test_acount_simple_condition(async_session, engine):
    domain = [["status", "=", "CONFIRMED"]]
    assert await engine.acount(async_session, domain=domain) == 2


@pytest.mark.asyncio
async def test_acount_m2o_path(async_session, engine):
    domain = [["customer.name", "=", "Alice"]]
    assert await engine.acount(async_session, domain=domain) == 1


@pytest.mark.asyncio
async def test_acount_n_level_path(async_session, engine):
    domain = [["customer.city.country.name", "=", "India"]]
    assert await engine.acount(async_session, domain=domain) == 1
