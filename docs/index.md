# AxiomQuery

**Specification-based query and aggregation engine for SQLAlchemy 2.0 ORM models.**

Define filters as composable data — JSON lists, dicts, or Python AST nodes — and execute
them against any ORM model without writing raw SQL.

```python
from axiom_query import QueryEngine

engine = QueryEngine(Order)

with Session(db) as session:
    records = engine.list(session, domain=[["status", "=", "CONFIRMED"]])
```

## Why AxiomQuery

- **Filters as data** — a *domain* is a JSON-serialisable expression, easy to store, pass
  over the wire, and build from a UI.
- **Zero-config schema** — `QueryEngine` derives everything it needs from
  `inspect(model_class)`; no separate descriptor, no DB connection at construction.
- **Logical composition** — implicit-AND lists plus explicit `and` / `or` / `not`, nested
  arbitrarily.
- **Relational dot-notation** — filter and group across `M2O` and `O2M` relationships to any
  depth (`customer.city.country.name`).
- **Grouped aggregation** — an Odoo-style [`read_group`](guide/aggregation.md) with date
  bucketing, child aggregates, `HAVING`, and per-group `__domain` drill-down.
- **Counting** — `count` returns how many records match a domain via `SELECT COUNT(*)`,
  without fetching any rows.
- **Streaming** — [`search`](guide/streaming-search.md) iterates large result sets with a
  server-side cursor.
- **Sync + async** — every method has an `a`-prefixed async twin.
- **Fail fast** — invalid fields and operators raise `QueryError` *before* hitting the
  database.

## Install

```bash
pip install AxiomQuery
```

Requires Python 3.12+ and SQLAlchemy 2.0+.

## Quick start

```python
from axiom_query import QueryEngine

engine = QueryEngine(Order)   # inspect() once — no DB connection at construction

with Session(db) as session:
    # filtered records
    records = engine.list(session, domain=[["status", "=", "CONFIRMED"]])

    # how many match — no rows fetched
    n = engine.count(session, domain=[["status", "=", "CONFIRMED"]])

    # grouped aggregation
    groups, total = engine.read_group(
        session,
        groupby=["status"],
        aggregates=["__count", "total:sum"],
    )
```

## Next steps

- [Getting Started](getting-started.md) — install, define a model, run your first query.
- [Domain Filter Syntax](guide/domain-syntax.md) — the full filter language.
- [Aggregation & read_group](guide/aggregation.md) — grouping and aggregates.
- [Relational Filtering](guide/relational-filtering.md) — dot-notation across relationships.
- [Philosophy](philosophy.md) — the ideas behind the design, including the Odoo influence.
