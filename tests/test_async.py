"""Tests for async QueryEngine variants — slice 11."""

from __future__ import annotations

import pytest

from conftest import Order


@pytest.mark.asyncio
async def test_alist_returns_all(async_session, engine):
    records = await engine.alist(async_session)
    assert len(records) == 3


@pytest.mark.asyncio
async def test_aread_group(async_session, engine):
    groups, total = await engine.aread_group(
        async_session, groupby=["status"], aggregates=["__count"]
    )
    assert total == 2
