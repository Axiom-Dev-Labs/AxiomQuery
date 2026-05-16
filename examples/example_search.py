"""Synchronous streaming example — QueryEngine.search().

Demonstrates:
  - Streaming iteration over the full result set with bounded memory
  - Domain filters (single condition, AND, OR, M2O-style is not used here —
    see example_sync.py for the full domain coverage)
  - order_by
  - Memory comparison against ``list()`` via tracemalloc

Prerequisites:
    uv run --package AxiomQuery python examples/generate_orders_csv.py
    uv run --package AxiomQuery python examples/load_csv_to_db.py

Run:
    uv run --package AxiomQuery python examples/example_search.py

Note on driver: SQLite does not support true server-side cursors, so this
example demonstrates the API and iteration semantics. Real per-batch streaming
benefit shows up against PostgreSQL with psycopg2.
"""

from __future__ import annotations

import time
import tracemalloc

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from axiom_query import QueryEngine
from orders_model import DB_PATH, Order


def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print("─" * 60)


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"{DB_PATH} not found — run generate_orders_csv.py and "
            "load_csv_to_db.py first"
        )

    db = create_engine(f"sqlite:///{DB_PATH}")
    engine = QueryEngine(Order)

    with Session(db) as session:
        # ── 1. Basic streaming iteration ─────────────────────────────────
        section("1. search() — stream every order, count matching status")

        confirmed_count = 0
        started = time.perf_counter()
        for order in engine.search(session, domain=[["status", "=", "CONFIRMED"]]):
            confirmed_count += 1
        elapsed = time.perf_counter() - started
        print(f"  CONFIRMED orders: {confirmed_count:,}  ({elapsed:.3f}s)")

        # ── 2. Streaming with order_by ───────────────────────────────────
        section("2. search() — order_by total desc, take top 5 with break")

        top_5: list[Order] = []
        for order in engine.search(session, order_by=[["total", "desc"]]):
            top_5.append(order)
            if len(top_5) == 5:
                break  # streaming lets us stop early
        for o in top_5:
            print(f"  {o}")

        # ── 3. Aggregate without loading into memory ─────────────────────
        section("3. search() — sum totals per customer (streaming aggregate)")

        per_customer: dict[str, int] = {}
        for order in engine.search(session, domain=[["status", "=", "SHIPPED"]]):
            per_customer[order.customer_name] = (
                per_customer.get(order.customer_name, 0) + order.total
            )
        for name in sorted(per_customer):
            print(f"  {name:>8}: {per_customer[name]:>12,}")

        # ── 4. Memory comparison: search() vs list() ─────────────────────
        section("4. search() vs list() — peak memory comparison")

        # search(): iterate without retaining
        session.expunge_all()
        tracemalloc.start()
        n = 0
        for _ in engine.search(session):
            n += 1
        _, search_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        print(f"  search()  iterated {n:,} rows, peak memory: {search_peak / 1024:>10,.1f} KB")

        # list(): materialise everything
        session.expunge_all()
        tracemalloc.start()
        records = engine.list(session)
        _, list_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        print(f"  list()    held    {len(records):,} rows, peak memory: {list_peak / 1024:>10,.1f} KB")

        ratio = list_peak / search_peak if search_peak else float("inf")
        print(f"  list() / search() peak ratio: {ratio:.1f}x")
        print(
            "\n  Note: SQLite buffers the result set on the driver side, so the "
            "gap is modest.\n  Against PostgreSQL the ratio grows roughly linearly "
            "with row count."
        )


if __name__ == "__main__":
    main()
