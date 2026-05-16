"""Shared ORM model for the search / asearch examples."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


DATA_DIR = Path(__file__).parent / "orders_data"
CSV_PATH = DATA_DIR / "orders.csv"
DB_PATH = DATA_DIR / "orders.db"


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    total: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    customer_name: Mapped[str] = mapped_column(String(100))

    def __repr__(self) -> str:
        return (
            f"Order(id={self.id}, status={self.status!r}, total={self.total}, "
            f"customer={self.customer_name!r})"
        )
