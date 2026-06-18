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


class Country(Base):
    __tablename__ = "countries"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


class City(Base):
    __tablename__ = "cities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    country_id: Mapped[Optional[int]] = mapped_column(ForeignKey("countries.id"), nullable=True)
    country: Mapped[Optional["Country"]] = relationship()


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    city_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cities.id"), nullable=True)
    city: Mapped[Optional["City"]] = relationship()


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(100))


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
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    product: Mapped[Optional["Product"]] = relationship()
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
        india = Country(id=1, name="India")
        usa = Country(id=2, name="USA")
        sess.add_all([india, usa])
        sess.flush()

        mumbai = City(id=1, name="Mumbai", country_id=1)
        nyc = City(id=2, name="New York", country_id=2)
        sess.add_all([mumbai, nyc])
        sess.flush()

        # p2/p3 categories chosen so exactly order 2 has an "Electronics" line
        p1 = Product(id=1, name="Widget A", category="Hardware")
        p2 = Product(id=2, name="Widget B", category="Hardware")
        p3 = Product(id=3, name="Gadget", category="Electronics")
        sess.add_all([p1, p2, p3])
        sess.flush()

        c1 = Customer(id=1, name="Alice", city_id=1)  # Mumbai, India
        c2 = Customer(id=2, name="Bob", city_id=2)  # New York, USA
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
        l1 = OrderLine(order_id=1, product_name="Widget A", quantity=2, unit_price=50, product_id=1)
        l2 = OrderLine(order_id=1, product_name="Widget B", quantity=3, unit_price=50, product_id=2)
        # Order 2 lines: qty=1 unit_price=200 (Gadget → Electronics)
        l3 = OrderLine(order_id=2, product_name="Gadget", quantity=1, unit_price=200, product_id=3)
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
        sess.add_all([Country(id=1, name="India"), Country(id=2, name="USA")])
        await sess.flush()
        sess.add_all([City(id=1, name="Mumbai", country_id=1), City(id=2, name="New York", country_id=2)])
        await sess.flush()
        sess.add_all([
            Product(id=1, name="Widget A", category="Hardware"),
            Product(id=2, name="Widget B", category="Hardware"),
            Product(id=3, name="Gadget", category="Electronics"),
        ])
        await sess.flush()

        c1 = Customer(id=1, name="Alice", city_id=1)
        c2 = Customer(id=2, name="Bob", city_id=2)
        sess.add_all([c1, c2])
        await sess.flush()

        o1 = Order(id=1, status="CONFIRMED", total=100, created_at=datetime(2026, 1, 15), customer_id=1)
        o2 = Order(id=2, status="CONFIRMED", total=200, created_at=datetime(2026, 2, 20), customer_id=2)
        o3 = Order(id=3, status="DRAFT", total=50, created_at=datetime(2026, 1, 25), customer_id=None)
        sess.add_all([o1, o2, o3])
        await sess.flush()

        l1 = OrderLine(order_id=1, product_name="Widget A", quantity=2, unit_price=50, product_id=1)
        l2 = OrderLine(order_id=1, product_name="Widget B", quantity=3, unit_price=50, product_id=2)
        l3 = OrderLine(order_id=2, product_name="Gadget", quantity=1, unit_price=200, product_id=3)
        sess.add_all([l1, l2, l3])
        await sess.commit()

    return async_db_engine


@pytest.fixture
async def async_session(seeded_async_engine):
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(seeded_async_engine) as sess:
        yield sess
