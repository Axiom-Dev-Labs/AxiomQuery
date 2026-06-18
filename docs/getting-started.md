# Getting Started

This page takes you from install to your first successful query.

## Install

```bash
pip install AxiomQuery
```

Requires **Python 3.12+** and **SQLAlchemy 2.0+**. AxiomQuery has no other runtime
dependencies — it works against any SQLAlchemy ORM model and any database SQLAlchemy
supports.

## Define a model

AxiomQuery works with ordinary SQLAlchemy 2.0 declarative models. The examples throughout
this guide use a small order domain — an `Order` with related `Customer` and a collection of
`OrderLine` rows:

```python
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"))
    customer: Mapped[Optional["Customer"]] = relationship()           # M2O
    lines: Mapped[List["OrderLine"]] = relationship(back_populates="order")  # O2M


class OrderLine(Base):
    __tablename__ = "order_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_name: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column()
    unit_price: Mapped[int] = mapped_column()
    order: Mapped["Order"] = relationship(back_populates="lines")
```

## Construct the engine

A `QueryEngine` is bound to one model class and derives its schema once via
`inspect()` — there is **no database connection at construction time**:

```python
from axiom_query import QueryEngine

engine = QueryEngine(Order)
```

You can keep a single engine instance around for the lifetime of your app and reuse it
across requests; it holds no session or connection state.

## Your first query

Pass a caller-owned `Session` to each call. `list()` returns a materialised list of ORM
instances:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

db = create_engine("sqlite:///:memory:")
Base.metadata.create_all(db)

with Session(db) as session:
    # ... add some orders ...

    confirmed = engine.list(session, domain=[["status", "=", "CONFIRMED"]])
    for order in confirmed:
        print(order.id, order.total)
```

The `domain` argument is the heart of AxiomQuery — a filter expressed as plain data. The
example above reads as "status equals CONFIRMED". Pass `domain=None` (or omit it) to return
all records.

To find out *how many* records match a domain without fetching them, use `count()` — it
issues a `SELECT COUNT(*)` and returns an `int`:

```python
    n = engine.count(session, domain=[["status", "=", "CONFIRMED"]])
```

## Next steps

- [Domain Filter Syntax](guide/domain-syntax.md) — every operator and composition form.
- [Aggregation & read_group](guide/aggregation.md) — grouped counts and sums.
- [Relational Filtering](guide/relational-filtering.md) — filter across `customer` and `lines`.

## Runnable examples

Self-contained, runnable scripts live in [`examples/`](https://github.com/Axiom-Dev-Labs/AxiomQuery/tree/main/examples):

```bash
python examples/example_sync.py
python examples/example_async.py
```

Both seed an in-memory SQLite database and walk through every feature: simple filters,
`AND` / `OR` / `NOT`, nested composition, child + N-level relational filtering, pagination,
and `read_group` with domains, date granularity, child aggregation, `HAVING`, and `__domain`
drill-down.
