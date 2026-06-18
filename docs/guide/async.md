# Async Usage

Every `QueryEngine` method has an `a`-prefixed async twin with an identical signature and
return shape. Pass an `AsyncSession` instead of a `Session`.

| Sync | Async |
|------|-------|
| `list` | `alist` |
| `count` | `acount` |
| `search` | `asearch` |
| `read_group` | `aread_group` |

The engine itself is constructed the same way — `QueryEngine(Order)` does pure `inspect()`
work and holds no connection, so a single instance is safe to share across sync and async
code.

## Setup

Use an async driver and an async engine. For production PostgreSQL use **asyncpg**; for local
development and tests, **aiosqlite** works well:

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from axiom_query import QueryEngine

db = create_async_engine("sqlite+aiosqlite:///:memory:")

async with db.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)

engine = QueryEngine(Order)
```

## Querying

```python
async with AsyncSession(db) as session:
    # filtered records
    records = await engine.alist(session, domain=[["status", "=", "CONFIRMED"]])

    # how many match — no rows fetched
    n = await engine.acount(session, domain=[["status", "=", "CONFIRMED"]])

    # grouped aggregation
    groups, total = await engine.aread_group(
        session,
        groupby=["status"],
        aggregates=["__count", "total:sum"],
    )

    # __domain drill-down
    for group in groups:
        rows = await engine.alist(session, domain=group["__domain"])
```

## Streaming

`asearch` returns an async iterator — `await` the call, then consume it with `async for`:

```python
async for order in await engine.asearch(session, domain=[["status", "=", "CONFIRMED"]]):
    await process(order)
```

See [Streaming & Search](streaming-search.md) for the single-pass and driver caveats (true
server-side streaming needs asyncpg; aiosqlite iterates correctly without it).

## Runnable example

[`examples/example_async.py`](https://github.com/Axiom-Dev-Labs/AxiomQuery/blob/main/examples/example_async.py)
mirrors the sync example end-to-end against an in-memory async SQLite database.
