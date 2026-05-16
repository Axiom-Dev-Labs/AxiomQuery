"""Generate a CSV of orders for the search / asearch examples.

Run:
    uv run --package AxiomQuery python examples/generate_orders_csv.py

Writes ``examples/orders_data/orders.csv`` (default 50,000 rows). Override the
row count with the ``N_ROWS`` env var, e.g. ``N_ROWS=1000000``.
"""

from __future__ import annotations

import csv
import os
import random
from datetime import datetime, timedelta

from orders_model import CSV_PATH, DATA_DIR


STATUSES = ["DRAFT", "CONFIRMED", "SHIPPED", "CANCELLED"]
STATUS_WEIGHTS = [0.10, 0.50, 0.30, 0.10]
CUSTOMER_NAMES = [
    "Alice", "Bob", "Carol", "Dave", "Eve",
    "Frank", "Grace", "Henry", "Iris", "Jack",
]


def main(n_rows: int = 50_000, seed: int = 42) -> None:
    random.seed(seed)
    DATA_DIR.mkdir(exist_ok=True)

    base_date = datetime(2025, 1, 1)

    with CSV_PATH.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "status", "total", "created_at", "customer_name"])

        for i in range(1, n_rows + 1):
            status = random.choices(STATUSES, weights=STATUS_WEIGHTS)[0]
            total = random.randint(10, 10_000)
            days_offset = random.randint(0, 365)
            created_at = (base_date + timedelta(days=days_offset)).isoformat()
            customer = random.choice(CUSTOMER_NAMES)
            writer.writerow([i, status, total, created_at, customer])

    print(f"Wrote {n_rows:,} orders to {CSV_PATH}")


if __name__ == "__main__":
    n = int(os.environ.get("N_ROWS", "50000"))
    main(n_rows=n)
