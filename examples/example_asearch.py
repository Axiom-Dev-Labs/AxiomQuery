"""Asynchronous streaming example — QueryEngine.asearch().

Mirrors example_search.py using AsyncSession and ``async for``.

Prerequisites:
    uv run --package AxiomQuery python examples/generate_orders_csv.py
    uv run --package AxiomQuery python examples/load_csv_to_db.py

Run:
    uv run --package AxiomQuery python examples/example_asearch.py

Note on driver: aiosqlite (used here for portability) does not support true
server-side cursors. For real per-batch streaming benefit, use asyncpg against
PostgreSQL.
"""

from __future__ import annotations

import asyncio
import time
import tracemalloc

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from axiom_query import QueryEngine
from orders_model import DB_PATH, Order


def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print("─" * 60)


async def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"{DB_PATH} not found — run generate_orders_csv.py and "
            "load_csv_to_db.py first"
        )

    db = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}")
    engine = QueryEngine(Order)

    async with AsyncSession(db) as session:
        # ── 1. Basic async streaming iteration ───────────────────────────
        section("1. asearch() — stream every order, count matching status")

        confirmed_count = 0
        started = time.perf_counter()
        result = await engine.asearch(session, domain=[["status", "=", "CONFIRMED"]])
        async for order in result:
            confirmed_count += 1
        elapsed = time.perf_counter() - started
        print(f"  CONFIRMED orders: {confirmed_count:,}  ({elapsed:.3f}s)")

        # ── 2. Streaming with order_by + early break ─────────────────────
        section("2. asearch() — order_by total desc, take top 5 with break")

        top_5: list[Order] = []
        result = await engine.asearch(session, order_by=[["total", "desc"]])
        async for order in result:
            top_5.append(order)
            if len(top_5) == 5:
                break
        for o in top_5:
            print(f"  {o}")

        # ── 3. Aggregate without loading into memory ─────────────────────
        section("3. asearch() — sum totals per customer (streaming aggregate)")

        per_customer: dict[str, int] = {}
        result = await engine.asearch(session, domain=[["status", "=", "SHIPPED"]])
        async for order in result:
            per_customer[order.customer_name] = (
                per_customer.get(order.customer_name, 0) + order.total
            )
        for name in sorted(per_customer):
            print(f"  {name:>8}: {per_customer[name]:>12,}")

        # ── 4. Memory comparison: asearch() vs alist() ───────────────────
        section("4. asearch() vs alist() — peak memory comparison")

        session.expunge_all()
        tracemalloc.start()
        n = 0
        result = await engine.asearch(session)
        async for _ in result:
            n += 1
        _, asearch_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        print(f"  asearch() iterated {n:,} rows, peak memory: {asearch_peak / 1024:>10,.1f} KB")

        session.expunge_all()
        tracemalloc.start()
        records = await engine.alist(session)
        _, alist_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        print(f"  alist()   held    {len(records):,} rows, peak memory: {alist_peak / 1024:>10,.1f} KB")

        ratio = alist_peak / asearch_peak if asearch_peak else float("inf")
        print(f"  alist() / asearch() peak ratio: {ratio:.1f}x")

    await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
