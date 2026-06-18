# Streaming & Search

`search` streams results instead of materialising them. Use it to process large result sets
row-by-row without loading everything into memory at once.

## `search` vs `list`

| | `list` | `search` |
|---|--------|----------|
| Returns | a materialised `list` | an **iterator** of ORM instances |
| Memory | holds every row | one batch at a time |
| `limit` / `offset` | supported | **not** supported |
| `len()` / indexing | yes | no — single-pass |
| Use when | you need a page, a count, or random access | you need to process **every** match |

```python
# materialised page
page = engine.list(session, domain=[["status", "=", "CONFIRMED"]], limit=20)

# stream every match
for order in engine.search(session, domain=[["status", "=", "CONFIRMED"]]):
    process(order)
```

## How streaming works

`search` executes with SQLAlchemy's `yield_per` set to a fixed prefetch size of **1000**
rows, pulling results from a server-side cursor in batches. It accepts a `domain` and
`order_by` but deliberately omits `limit` / `offset` — it is designed to walk the full result
set.

!!! warning "Single-pass"
    The returned iterator is consumed once. Don't store it for reuse, call `len()` on it, or
    index into it. If you need any of those, use `list()`.

## Driver support

True server-side streaming requires a database driver that supports server-side cursors —
**psycopg2** or **asyncpg** (PostgreSQL). With SQLite (`sqlite` / `aiosqlite`), iteration
still works and yields the same correct results, but without true driver-level streaming.

## Async: `asearch`

`asearch` is the async twin. It returns an async iterator, consumed with `async for`:

```python
async for order in await engine.asearch(session, domain=[["status", "=", "CONFIRMED"]]):
    await process(order)
```

The same constraints apply: single-pass, no `limit` / `offset`, batches of 1000 from a
server-side cursor (asyncpg for true streaming; aiosqlite iterates correctly without it). See
[Async Usage](async.md) for setup.
