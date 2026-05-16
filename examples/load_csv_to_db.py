"""Load orders.csv into a SQLite database file used by the search examples.

Run:
    uv run --package AxiomQuery python examples/load_csv_to_db.py

Prerequisite: run ``generate_orders_csv.py`` first to produce the CSV. This
script (re)creates ``examples/orders_data/orders.db`` and bulk-inserts the rows
in batches of 5,000.
"""

from __future__ import annotations

import csv
import time
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from orders_model import Base, CSV_PATH, DB_PATH, Order


BATCH_SIZE = 5_000


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"{CSV_PATH} not found — run generate_orders_csv.py first"
        )

    if DB_PATH.exists():
        DB_PATH.unlink()

    db = create_engine(f"sqlite:///{DB_PATH}")
    Base.metadata.create_all(db)

    started = time.perf_counter()
    rows_loaded = 0

    with CSV_PATH.open() as f, Session(db) as session:
        reader = csv.DictReader(f)
        batch: list[Order] = []

        for row in reader:
            batch.append(
                Order(
                    id=int(row["id"]),
                    status=row["status"],
                    total=int(row["total"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    customer_name=row["customer_name"],
                )
            )
            if len(batch) >= BATCH_SIZE:
                session.add_all(batch)
                session.commit()
                rows_loaded += len(batch)
                batch.clear()

        if batch:
            session.add_all(batch)
            session.commit()
            rows_loaded += len(batch)

    elapsed = time.perf_counter() - started
    print(f"Loaded {rows_loaded:,} rows into {DB_PATH} in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
