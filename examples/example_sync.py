"""Synchronous usage examples for axiom_query.

Demonstrates all domain condition styles:
  - Simple equality / comparison
  - AND  — all conditions must hold
  - OR   — any condition must hold
  - NOT  — negation
  - Combined — nested AND / OR / NOT
  - Child-field EXISTS filtering (O2M)
  - Many-to-One field filtering (M2O EXISTS subquery)
  - list() options: limit, offset, order_by
  - read_group() with domain, date granularity, child aggregate, HAVING
  - __domain drill-down: group result → list of matching records

Run:
    uv run --package AxiomQuery python examples/example_sync.py
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from axiom_query import QueryEngine


# ── Models ────────────────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    pass


class Country(Base):
    __tablename__ = "countries"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


class City(Base):
    __tablename__ = "cities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    country_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("countries.id"), nullable=True
    )
    country: Mapped[Optional["Country"]] = relationship()


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(100))


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    city_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cities.id"), nullable=True
    )
    city: Mapped[Optional["City"]] = relationship()

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
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.id"), nullable=True
    )
    product: Mapped[Optional["Product"]] = relationship()
    order: Mapped["Order"] = relationship(back_populates="lines")


# ── Seed data ─────────────────────────────────────────────────────────────────


def seed(session: Session) -> None:
    session.add_all(
        [
            Country(id=1, name="India"),
            Country(id=2, name="USA"),
        ]
    )
    session.flush()
    session.add_all(
        [
            City(id=1, name="Mumbai", country_id=1),
            City(id=2, name="New York", country_id=2),
        ]
    )
    session.flush()
    session.add_all(
        [
            Product(id=1, name="Widget A", category="Hardware"),
            Product(id=2, name="Widget B", category="Hardware"),
            Product(id=3, name="Gadget", category="Electronics"),
            Product(id=4, name="Accessory", category="Electronics"),
        ]
    )
    session.flush()
    session.add_all(
        [
            Customer(id=1, name="Joy", city_id=1),  # Mumbai, India
            Customer(id=2, name="Bob", city_id=2),  # New York, USA
        ]
    )
    session.flush()
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
    session.flush()
    session.add_all(
        [
            OrderLine(order_id=1, product_name="Widget A", quantity=2, unit_price=50, product_id=1),
            OrderLine(order_id=1, product_name="Widget B", quantity=3, unit_price=50, product_id=2),
            OrderLine(order_id=2, product_name="Gadget", quantity=1, unit_price=200, product_id=3),
            OrderLine(order_id=4, product_name="Accessory", quantity=5, unit_price=15, product_id=4),
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

        # ── Section 8: M2O field — EXISTS on referenced table ────────────

        section("8. M2O field filtering (EXISTS on referenced table)")

        show(
            "orders where customer.name = 'Joy'",
            engine.list(session, domain=[["customer.name", "=", "Joy"]]),
        )

        show(
            "orders where customer.name ilike '%ob%'",
            engine.list(session, domain=[["customer.name", "ilike", "%ob%"]]),
        )

        show(
            "CONFIRMED orders for Joy (M2O + scalar)",
            engine.list(
                session,
                domain=[
                    ["customer.name", "=", "Joy"],
                    ["status", "=", "CONFIRMED"],
                ],
            ),
        )

        # ── Section 8b: N-level relational filtering ─────────────────────

        section("8b. N-level relational filtering (deep dot-notation)")

        show(
            "2-level M2O — orders where customer.city.name = 'Mumbai'",
            engine.list(session, domain=[["customer.city.name", "=", "Mumbai"]]),
        )

        show(
            "3-level M2O — orders where customer.city.country.name ilike '%Ind%'",
            engine.list(
                session, domain=[["customer.city.country.name", "ilike", "%Ind%"]]
            ),
        )

        show(
            "O2M → M2O — orders with a line whose product.category = 'Electronics'",
            engine.list(session, domain=[["lines.product.category", "=", "Electronics"]]),
        )

        # ── Section 9: list() options ─────────────────────────────────────

        section("9. list() — limit, offset, order_by")

        show(
            "top 2 by total desc",
            engine.list(session, order_by=[["total", "desc"]], limit=2),
        )

        show(
            "page 2 (offset=2, limit=2) ordered by id asc",
            engine.list(session, order_by=[["id", "asc"]], limit=2, offset=2),
        )

        # ── Section 9: read_group — basic ─────────────────────────────────

        section("10. read_group — basic groupby + count")

        groups, total = engine.read_group(
            session,
            groupby=["status"],
            aggregates=["__count"],
            order_by=[["__count", "desc"]],
        )
        show_groups("count per status (desc)", groups, total)

        # ── Section 10: read_group with domain ───────────────────────────

        section("11. read_group with domain filter")

        groups, total = engine.read_group(
            session,
            groupby=["status"],
            aggregates=["__count", "total:sum"],
            domain=[["status", "!=", "CANCELLED"]],
        )
        show_groups("count + sum(total) excluding CANCELLED", groups, total)

        # ── Section 11: read_group — date granularity ─────────────────────

        section("12. read_group — date granularity (month)")

        groups, total = engine.read_group(
            session,
            groupby=["created_at:month"],
            aggregates=["__count", "total:sum"],
            order_by=[["created_at__month", "asc"]],
        )
        show_groups("orders grouped by month", groups, total)

        # ── Section 12: read_group — child aggregate (LEFT JOIN) ──────────

        section("13. read_group — child aggregate (LEFT JOIN)")

        groups, total = engine.read_group(
            session,
            groupby=["status"],
            aggregates=["__count", "lines.quantity:sum"],
        )
        show_groups("sum of line quantities per status", groups, total)

        # ── Section 12b: read_group — N-level deep groupby ───────────────

        section("13b. read_group — deep relational groupby (O2M → M2O)")

        groups, total = engine.read_group(
            session,
            groupby=["lines.product.category"],
            aggregates=["lines.quantity:sum"],
        )
        show_groups("sum of line quantities per product category", groups, total)

        # ── Section 13: read_group — HAVING ──────────────────────────────

        section("14. read_group — HAVING filter on aggregate")

        groups, total = engine.read_group(
            session,
            groupby=["status"],
            aggregates=["__count"],
            having=[["__count", ">", 1]],
        )
        show_groups("only groups with count > 1", groups, total)

        # ── Section 14: __domain drill-down ──────────────────────────────

        section("15. __domain drill-down — group → records")

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
