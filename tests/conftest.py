"""Test fixtures for axiom_query tests."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import pytest
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from axiom_query.engine import QueryEngine


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    total: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True)
    customer: Mapped[Optional["Customer"]] = relationship()
    lines: Mapped[List["OrderLine"]] = relationship(back_populates="order")


class OrderLine(Base):
    __tablename__ = "order_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_name: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column()
    unit_price: Mapped[int] = mapped_column()
    order: Mapped["Order"] = relationship(back_populates="lines")


@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def seeded_engine(db_engine):
    """Seed test data once per session."""
    with Session(db_engine) as sess:
        c1 = Customer(id=1, name="Alice")
        c2 = Customer(id=2, name="Bob")
        sess.add_all([c1, c2])
        sess.flush()

        o1 = Order(
            id=1,
            status="CONFIRMED",
            total=100,
            created_at=datetime(2026, 1, 15),
            customer_id=1,
        )
        o2 = Order(
            id=2,
            status="CONFIRMED",
            total=200,
            created_at=datetime(2026, 2, 20),
            customer_id=2,
        )
        o3 = Order(
            id=3,
            status="DRAFT",
            total=50,
            created_at=datetime(2026, 1, 25),
            customer_id=None,
        )
        sess.add_all([o1, o2, o3])
        sess.flush()

        # Order 1 lines: qty=2 unit_price=50; qty=3 unit_price=50
        l1 = OrderLine(order_id=1, product_name="Widget A", quantity=2, unit_price=50)
        l2 = OrderLine(order_id=1, product_name="Widget B", quantity=3, unit_price=50)
        # Order 2 lines: qty=1 unit_price=200
        l3 = OrderLine(order_id=2, product_name="Gadget", quantity=1, unit_price=200)
        # Order 3: no lines
        sess.add_all([l1, l2, l3])
        sess.commit()

    return db_engine


@pytest.fixture
def session(seeded_engine):
    with Session(seeded_engine) as sess:
        yield sess


@pytest.fixture(scope="session")
def engine():
    return QueryEngine(Order)


# ── Async fixtures ─────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def async_db_engine():
    from sqlalchemy.ext.asyncio import create_async_engine
    return create_async_engine("sqlite+aiosqlite:///:memory:")


@pytest.fixture(scope="session")
async def seeded_async_engine(async_db_engine):
    async with async_db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(async_db_engine) as sess:
        c1 = Customer(id=1, name="Alice")
        c2 = Customer(id=2, name="Bob")
        sess.add_all([c1, c2])
        await sess.flush()

        o1 = Order(id=1, status="CONFIRMED", total=100, created_at=datetime(2026, 1, 15), customer_id=1)
        o2 = Order(id=2, status="CONFIRMED", total=200, created_at=datetime(2026, 2, 20), customer_id=2)
        o3 = Order(id=3, status="DRAFT", total=50, created_at=datetime(2026, 1, 25), customer_id=None)
        sess.add_all([o1, o2, o3])
        await sess.flush()

        l1 = OrderLine(order_id=1, product_name="Widget A", quantity=2, unit_price=50)
        l2 = OrderLine(order_id=1, product_name="Widget B", quantity=3, unit_price=50)
        l3 = OrderLine(order_id=2, product_name="Gadget", quantity=1, unit_price=200)
        sess.add_all([l1, l2, l3])
        await sess.commit()

    return async_db_engine


@pytest.fixture
async def async_session(seeded_async_engine):
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(seeded_async_engine) as sess:
        yield sess
