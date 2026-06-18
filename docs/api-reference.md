# API Reference

Everything below is importable directly from `axiom_query`.

```python
from axiom_query import (
    QueryEngine,
    QueryError,
    Op,
    Condition, And, Or, Not, Bool, QuerySpec,
    parse_domain,
)
```

## `QueryEngine`

```python
QueryEngine(model_class: type)
```

Bound to one SQLAlchemy model. Derives its schema from `inspect(model_class)` at
construction — no database connection is opened. Reuse one instance across requests.

### Methods

All query methods take a caller-owned session as the first argument.

| Method | Returns | Description |
|--------|---------|-------------|
| `list(session, domain=None, limit=None, offset=None, order_by=None)` | `list` | Materialised records matching the domain. |
| `count(session, domain=None)` | `int` | Number of records matching the domain via `SELECT COUNT(*)` — no rows fetched. Ignores `limit`/`offset`/`order_by`. |
| `search(session, domain=None, order_by=None)` | iterator | Streams every matching record (server-side cursor, batches of 1000). No `limit`/`offset`. |
| `read_group(session, groupby, aggregates, domain=None, having=None, order_by=None, limit=None, offset=None)` | `tuple[list[dict], int]` | Grouped aggregation; each group dict carries a `__domain`. |
| `alist(...)` | `list` | Async `list`. |
| `acount(...)` | `int` | Async `count`. |
| `asearch(...)` | async iterator | Async `search`; consume with `async for`. |
| `aread_group(...)` | `tuple[list[dict], int]` | Async `read_group`. |

- `domain` — a [domain expression](guide/domain-syntax.md) or `None` (all records).
- `order_by` — `[["field", "asc"|"desc"], ...]`; in `read_group`, order by an alias.
- `groupby` — `["field", "field:granularity", ...]` (granularity: `day`/`week`/`month`/`quarter`/`year`).
- `aggregates` — `["__count", "field:func", ...]` (func: `count`/`sum`/`avg`/`min`/`max`).
- `having` — a domain over aggregate/groupby aliases (e.g. `[["total__sum", ">", 100]]`).

## `parse_domain`

```python
parse_domain(raw: Any) -> QuerySpec
```

Parses a JSON domain (list/dict/`None`) into the AST. Useful to validate or inspect a domain
without executing a query. Raises `QueryError` on malformed input.

## AST nodes

Immutable dataclasses forming the `QuerySpec` union. They compose with `&` (And), `|` (Or),
and `~` (Not):

| Node | Shape |
|------|-------|
| `Condition` | `Condition(field_path, operator, value)` |
| `And` | `And(left, right)` |
| `Or` | `Or(left, right)` |
| `Not` | `Not(operand)` |
| `Bool` | `Bool(value)` — constant true/false |
| `QuerySpec` | `Union` of the above |

## `Op`

A `str` `Enum` of the eleven operators: `=`, `!=`, `>`, `<`, `>=`, `<=`, `in`, `not in`,
`like`, `ilike`, `is_null`. Parse from a string (case-insensitive) with `Op.from_str(s)`.

## `QueryError`

Raised for invalid domains, fields, operators, and `HAVING` clauses — always *before* the
database is touched. Carries a `code` (e.g. `INVALID_FILTER_FIELD`, `INVALID_DOMAIN`) and a
human-readable `message`.

---

!!! tip "Optional: auto-generate from docstrings"
    To pull this reference straight from source docstrings, add the
    [`mkdocstrings[python]`](https://mkdocstrings.github.io/) plugin and replace this page
    with `::: axiom_query` directives.
