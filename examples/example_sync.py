"""Synchronous usage examples for axiom_query.

Demonstrates all domain condition styles:
  - Simple equality / comparison
  - AND  — all conditions must hold
  - OR   — any condition must hold
  - NOT  — negation
  - Combined — nested AND / OR / NOT
  - Child-field EXISTS filtering
  - list() options: limit, offset, order_by
  - read_group() with domain, date granularity, child aggregate, HAVING
  - __domain drill-down: group result → list of matching records

Run:
    uv run --package AxiomQuery python examples/example_sync.py
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import DateTime, ForeignKey, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from axiom_query import QueryEngine


# ── Models ────────────────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    total: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime)
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


def seed(session: Session) -> None:
    session.add_all(
        [
            Order(
                id=1, status="CONFIRMED", total=100, created_at=datetime(2026, 1, 15)
            ),
            Order(
                id=2, status="CONFIRMED", total=200, created_at=datetime(2026, 2, 20)
            ),
            Order(id=3, status="DRAFT", total=50, created_at=datetime(2026, 1, 25)),
            Order(id=4, status="CANCELLED", total=75, created_at=datetime(2026, 3, 10)),
        ]
    )
    session.flush()
    session.add_all(
        [
            OrderLine(order_id=1, product_name="Widget A", quantity=2, unit_price=50),
            OrderLine(order_id=1, product_name="Widget B", quantity=3, unit_price=50),
            OrderLine(order_id=2, product_name="Gadget", quantity=1, unit_price=200),
            OrderLine(order_id=4, product_name="Accessory", quantity=5, unit_price=15),
        ]
    )
    session.commit()


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


def main() -> None:
    db = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(db)

    # QueryEngine is constructed once — pure inspect(), no DB connection
    engine = QueryEngine(Order)

    with Session(db) as session:
        seed(session)

        # ── Section 1: Basic list ─────────────────────────────────────────

        section("1. list() — no domain (all records)")
        show("all orders", engine.list(session))

        # ── Section 2: Simple conditions ─────────────────────────────────

        section("2. Simple equality and comparison")

        show(
            "status = CONFIRMED",
            engine.list(session, domain=[["status", "=", "CONFIRMED"]]),
        )

        show(
            "total > 75",
            engine.list(session, domain=[["total", ">", 75]]),
        )

        show(
            "status in [DRAFT, CANCELLED]",
            engine.list(session, domain=[["status", "in", ["DRAFT", "CANCELLED"]]]),
        )

        show(
            "status is_null False (non-null statuses)",
            engine.list(session, domain=[["status", "is_null", False]]),
        )

        # ── Section 3: AND — multiple conditions in a list ───────────────

        section("3. AND — list of conditions (implicitly ANDed)")

        show(
            "status = CONFIRMED AND total >= 150",
            engine.list(
                session,
                domain=[
                    ["status", "=", "CONFIRMED"],
                    ["total", ">=", 150],
                ],
            ),
        )

        show(
            "explicit {'and': [...]}",
            engine.list(
                session,
                domain={
                    "and": [
                        ["status", "=", "CONFIRMED"],
                        ["total", ">=", 150],
                    ]
                },
            ),
        )

        # ── Section 4: OR ─────────────────────────────────────────────────

        section("4. OR — any condition must hold")

        show(
            "status = DRAFT OR status = CANCELLED",
            engine.list(
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
            "total < 60 OR total > 150",
            engine.list(
                session,
                domain={
                    "or": [
                        ["total", "<", 60],
                        ["total", ">", 150],
                    ]
                },
            ),
        )

        # ── Section 5: NOT ────────────────────────────────────────────────

        section("5. NOT — negation")

        show(
            "NOT status = CANCELLED",
            engine.list(session, domain={"not": ["status", "=", "CANCELLED"]}),
        )

        show(
            "NOT (status in [DRAFT, CANCELLED])",
            engine.list(
                session,
                domain={
                    "not": {
                        "or": [
                            ["status", "=", "DRAFT"],
                            ["status", "=", "CANCELLED"],
                        ]
                    }
                },
            ),
        )

        # ── Section 6: Combined AND + OR + NOT ───────────────────────────

        section("6. Combined — nested AND / OR / NOT")

        # (status = CONFIRMED OR status = DRAFT) AND total >= 50 AND NOT total = 50
        show(
            "(status = CONFIRMED OR DRAFT) AND total >= 50 AND NOT total = 50",
            engine.list(
                session,
                domain=[
                    {
                        "or": [
                            ["status", "=", "CONFIRMED"],
                            ["status", "=", "DRAFT"],
                        ]
                    },
                    ["total", ">=", 50],
                    {"not": ["total", "=", 50]},
                ],
            ),
        )

        # CONFIRMED with total > 100, OR any CANCELLED order
        show(
            "(CONFIRMED AND total > 100) OR CANCELLED",
            engine.list(
                session,
                domain={
                    "or": [
                        {
                            "and": [
                                ["status", "=", "CONFIRMED"],
                                ["total", ">", 100],
                            ]
                        },
                        ["status", "=", "CANCELLED"],
                    ]
                },
            ),
        )

        # ── Section 7: Child field — EXISTS subquery ──────────────────────

        section("7. Child field filtering (EXISTS subquery)")

        show(
            "orders that have at least one line with quantity > 2",
            engine.list(session, domain=[["lines.quantity", ">", 2]]),
        )

        show(
            "orders with any line for product_name ilike '%widget%'",
            engine.list(session, domain=[["lines.product_name", "ilike", "%widget%"]]),
        )

        show(
            "CONFIRMED orders with any line quantity > 2",
            engine.list(
                session,
                domain=[
                    ["status", "=", "CONFIRMED"],
                    ["lines.quantity", ">", 2],
                ],
            ),
        )

        # ── Section 8: list() options ─────────────────────────────────────

        section("8. list() — limit, offset, order_by")

        show(
            "top 2 by total desc",
            engine.list(session, order_by=[["total", "desc"]], limit=2),
        )

        show(
            "page 2 (offset=2, limit=2) ordered by id asc",
            engine.list(session, order_by=[["id", "asc"]], limit=2, offset=2),
        )

        # ── Section 9: read_group — basic ─────────────────────────────────

        section("9. read_group — basic groupby + count")

        groups, total = engine.read_group(
            session,
            groupby=["status"],
            aggregates=["__count"],
            order_by=[["__count", "desc"]],
        )
        show_groups("count per status (desc)", groups, total)

        # ── Section 10: read_group with domain ───────────────────────────

        section("10. read_group with domain filter")

        groups, total = engine.read_group(
            session,
            groupby=["status"],
            aggregates=["__count", "total:sum"],
            domain=[["status", "!=", "CANCELLED"]],
        )
        show_groups("count + sum(total) excluding CANCELLED", groups, total)

        # ── Section 11: read_group — date granularity ─────────────────────

        section("11. read_group — date granularity (month)")

        groups, total = engine.read_group(
            session,
            groupby=["created_at:month"],
            aggregates=["__count", "total:sum"],
            order_by=[["created_at__month", "asc"]],
        )
        show_groups("orders grouped by month", groups, total)

        # ── Section 12: read_group — child aggregate (LEFT JOIN) ──────────

        section("12. read_group — child aggregate (LEFT JOIN)")

        groups, total = engine.read_group(
            session,
            groupby=["status"],
            aggregates=["__count", "lines.quantity:sum"],
        )
        show_groups("sum of line quantities per status", groups, total)

        # ── Section 13: read_group — HAVING ──────────────────────────────

        section("13. read_group — HAVING filter on aggregate")

        groups, total = engine.read_group(
            session,
            groupby=["status"],
            aggregates=["__count"],
            having=[["__count", ">", 1]],
        )
        show_groups("only groups with count > 1", groups, total)

        # ── Section 14: __domain drill-down ──────────────────────────────

        section("14. __domain drill-down — group → records")

        groups, _ = engine.read_group(
            session,
            groupby=["status"],
            aggregates=["__count"],
        )
        print()
        for group in groups:
            records = engine.list(session, domain=group["__domain"])
            status = group["status"]
            count = group["__count"]
            print(f"  Group status={status!r} (__count={count}) → drill-down records:")
            for r in records:
                print(f"    {r}")


if __name__ == "__main__":
    main()
