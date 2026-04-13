"""Asynchronous usage examples for axiom_query.

Mirrors example_sync.py but uses AsyncSession and the alist() / aread_group()
methods.  Demonstrates the same domain styles:
  - Simple equality / comparison
  - AND, OR, NOT
  - Combined nested conditions
  - Child-field EXISTS filtering (O2M)
  - Many-to-One field filtering (M2O EXISTS subquery)
  - alist() options: limit, offset, order_by
  - aread_group() with domain, date granularity, child aggregate, HAVING
  - __domain drill-down with alist()

Run:
    uv run --package AxiomQuery python examples/example_async.py
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from axiom_query import QueryEngine


# ── Models ────────────────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))

    def __repr__(self) -> str:
        return f"Customer(id={self.id}, name={self.name!r})"


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    total: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id"), nullable=True
    )
    customer: Mapped[Optional["Customer"]] = relationship()
    lines: Mapped[List["OrderLine"]] = relationship(back_populates="order")

    def __repr__(self) -> str:
        return f"Order(id={self.id}, status={self.status!r}, total={self.total})"


class OrderLine(Base):
    __tablename__ = "order_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_name: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column()
    unit_price: Mapped[int] = mapped_column()
    order: Mapped["Order"] = relationship(back_populates="lines")


# ── Seed data ─────────────────────────────────────────────────────────────────


async def seed(session: AsyncSession) -> None:
    session.add_all(
        [
            Customer(id=1, name="Joy"),
            Customer(id=2, name="Bob"),
        ]
    )
    await session.flush()
    session.add_all(
        [
            Order(
                id=1,
                status="CONFIRMED",
                total=100,
                created_at=datetime(2026, 1, 15),
                customer_id=1,
            ),
            Order(
                id=2,
                status="CONFIRMED",
                total=200,
                created_at=datetime(2026, 2, 20),
                customer_id=2,
            ),
            Order(
                id=3,
                status="DRAFT",
                total=50,
                created_at=datetime(2026, 1, 25),
                customer_id=1,
            ),
            Order(
                id=4,
                status="CANCELLED",
                total=75,
                created_at=datetime(2026, 3, 10),
                customer_id=None,
            ),
        ]
    )
    await session.flush()
    session.add_all(
        [
            OrderLine(order_id=1, product_name="Widget A", quantity=2, unit_price=50),
            OrderLine(order_id=1, product_name="Widget B", quantity=3, unit_price=50),
            OrderLine(order_id=2, product_name="Gadget", quantity=1, unit_price=200),
            OrderLine(order_id=4, product_name="Accessory", quantity=5, unit_price=15),
        ]
    )
    await session.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────


def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print("─" * 60)


def show(label: str, records) -> None:
    print(f"\n{label}:")
    for r in records:
        print(f"  {r}")


def show_groups(label: str, groups: list[dict], total: int) -> None:
    print(f"\n{label}  [total groups: {total}]:")
    for g in groups:
        domain = g.get("__domain")
        data = {k: v for k, v in g.items() if k != "__domain"}
        print(f"  {data}  __domain={domain}")


# ── Main ──────────────────────────────────────────────────────────────────────


async def main() -> None:
    db = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # QueryEngine is constructed once — pure inspect(), no DB connection
    engine = QueryEngine(Order)

    async with AsyncSession(db) as session:
        await seed(session)

        # ── Section 1: Basic alist ────────────────────────────────────────

        section("1. alist() — no domain (all records)")
        show("all orders", await engine.alist(session))

        # ── Section 2: Simple conditions ─────────────────────────────────

        section("2. Simple equality and comparison")

        show(
            "status = CONFIRMED",
            await engine.alist(session, domain=[["status", "=", "CONFIRMED"]]),
        )

        show(
            "total >= 100",
            await engine.alist(session, domain=[["total", ">=", 100]]),
        )

        show(
            "status not in [DRAFT, CANCELLED]",
            await engine.alist(
                session, domain=[["status", "not in", ["DRAFT", "CANCELLED"]]]
            ),
        )

        # ── Section 3: AND ────────────────────────────────────────────────

        section("3. AND — list of conditions (implicitly ANDed)")

        show(
            "status = CONFIRMED AND total > 100",
            await engine.alist(
                session,
                domain=[
                    ["status", "=", "CONFIRMED"],
                    ["total", ">", 100],
                ],
            ),
        )

        show(
            "explicit {'and': [...]}",
            await engine.alist(
                session,
                domain={
                    "and": [
                        ["status", "=", "CONFIRMED"],
                        ["total", ">", 100],
                    ]
                },
            ),
        )

        # ── Section 4: OR ─────────────────────────────────────────────────

        section("4. OR — any condition must hold")

        show(
            "status = DRAFT OR status = CANCELLED",
            await engine.alist(
                session,
                domain={
                    "or": [
                        ["status", "=", "DRAFT"],
                        ["status", "=", "CANCELLED"],
                    ]
                },
            ),
        )

        show(
            "total <= 75 OR total >= 200",
            await engine.alist(
                session,
                domain={
                    "or": [
                        ["total", "<=", 75],
                        ["total", ">=", 200],
                    ]
                },
            ),
        )

        # ── Section 5: NOT ────────────────────────────────────────────────

        section("5. NOT — negation")

        show(
            "NOT status = DRAFT",
            await engine.alist(session, domain={"not": ["status", "=", "DRAFT"]}),
        )

        show(
            "NOT (total > 100)",
            await engine.alist(session, domain={"not": ["total", ">", 100]}),
        )

        # ── Section 6: Combined AND + OR + NOT ───────────────────────────

        section("6. Combined — nested AND / OR / NOT")

        # NOT CANCELLED AND (status = CONFIRMED OR total < 60)
        show(
            "NOT CANCELLED AND (CONFIRMED OR total < 60)",
            await engine.alist(
                session,
                domain=[
                    {"not": ["status", "=", "CANCELLED"]},
                    {
                        "or": [
                            ["status", "=", "CONFIRMED"],
                            ["total", "<", 60],
                        ]
                    },
                ],
            ),
        )

        # (CONFIRMED AND total >= 100) OR (DRAFT AND total < 100)
        show(
            "(CONFIRMED AND total >= 100) OR (DRAFT AND total < 100)",
            await engine.alist(
                session,
                domain={
                    "or": [
                        {
                            "and": [
                                ["status", "=", "CONFIRMED"],
                                ["total", ">=", 100],
                            ]
                        },
                        {
                            "and": [
                                ["status", "=", "DRAFT"],
                                ["total", "<", 100],
                            ]
                        },
                    ]
                },
            ),
        )

        # CONFIRMED, not the cheap one, ordered and limited
        show(
            "CONFIRMED AND NOT total = 100  (combined + comparison)",
            await engine.alist(
                session,
                domain=[
                    ["status", "=", "CONFIRMED"],
                    {"not": ["total", "=", 100]},
                ],
            ),
        )

        # ── Section 7: Child field — EXISTS subquery ──────────────────────

        section("7. Child field filtering (EXISTS subquery)")

        show(
            "orders with at least one line quantity >= 3",
            await engine.alist(session, domain=[["lines.quantity", ">=", 3]]),
        )

        show(
            "orders with any line unit_price > 100",
            await engine.alist(session, domain=[["lines.unit_price", ">", 100]]),
        )

        show(
            "NOT CANCELLED AND has a line with quantity > 1",
            await engine.alist(
                session,
                domain=[
                    {"not": ["status", "=", "CANCELLED"]},
                    ["lines.quantity", ">", 1],
                ],
            ),
        )

        # ── Section 8: M2O field — EXISTS on referenced table ────────────

        section("8. M2O field filtering (EXISTS on referenced table)")

        show(
            "orders where customer.name = 'Joy'",
            await engine.alist(session, domain=[["customer.name", "=", "Joy"]]),
        )

        show(
            "orders where customer.name ilike '%ob%'",
            await engine.alist(session, domain=[["customer.name", "ilike", "%ob%"]]),
        )

        show(
            "CONFIRMED orders for Joy (M2O + scalar)",
            await engine.alist(
                session,
                domain=[
                    ["customer.name", "=", "Joy"],
                    ["status", "=", "CONFIRMED"],
                ],
            ),
        )

        # ── Section 9: alist() options ────────────────────────────────────

        section("9. alist() — limit, offset, order_by")

        show(
            "top 2 orders by total desc",
            await engine.alist(session, order_by=[["total", "desc"]], limit=2),
        )

        show(
            "page 2: offset=2, limit=2, order by id asc",
            await engine.alist(session, order_by=[["id", "asc"]], limit=2, offset=2),
        )

        show(
            "CONFIRMED orders sorted by total asc",
            await engine.alist(
                session,
                domain=[["status", "=", "CONFIRMED"]],
                order_by=[["total", "asc"]],
            ),
        )

        # ── Section 9: aread_group — basic ────────────────────────────────

        section("10. aread_group — basic groupby + count")

        groups, total = await engine.aread_group(
            session,
            groupby=["status"],
            aggregates=["__count"],
            order_by=[["__count", "desc"]],
        )
        show_groups("count per status (desc)", groups, total)

        # ── Section 10: aread_group with domain ───────────────────────────

        section("11. aread_group with domain filter")

        groups, total = await engine.aread_group(
            session,
            groupby=["status"],
            aggregates=["__count", "total:sum"],
            domain={"not": ["status", "=", "CANCELLED"]},
        )
        show_groups("count + sum(total) excluding CANCELLED", groups, total)

        # ── Section 11: aread_group — date granularity ────────────────────

        section("12. aread_group — date granularity (month)")

        groups, total = await engine.aread_group(
            session,
            groupby=["created_at:month"],
            aggregates=["__count", "total:sum"],
            order_by=[["created_at__month", "asc"]],
        )
        show_groups("orders grouped by month", groups, total)

        # ── Section 12: aread_group — child aggregate (LEFT JOIN) ─────────

        section("13. aread_group — child aggregate (LEFT JOIN)")

        groups, total = await engine.aread_group(
            session,
            groupby=["status"],
            aggregates=["__count", "lines.quantity:sum", "lines.unit_price:avg"],
        )
        show_groups("line qty sum + unit_price avg per status", groups, total)

        # ── Section 13: aread_group — HAVING ──────────────────────────────

        section("14. aread_group — HAVING filter on aggregate")

        groups, total = await engine.aread_group(
            session,
            groupby=["status"],
            aggregates=["__count", "total:sum"],
            having=[["total__sum", ">", 100]],
        )
        show_groups("groups where sum(total) > 100", groups, total)

        # ── Section 14: __domain drill-down with alist() ──────────────────

        section("15. __domain drill-down — group → records via alist()")

        groups, _ = await engine.aread_group(
            session,
            groupby=["status"],
            aggregates=["__count"],
        )
        print()
        for group in groups:
            records = await engine.alist(session, domain=group["__domain"])
            status = group["status"]
            count = group["__count"]
            print(f"  Group status={status!r} (__count={count}) → drill-down records:")
            for r in records:
                print(f"    {r}")


if __name__ == "__main__":
    asyncio.run(main())
