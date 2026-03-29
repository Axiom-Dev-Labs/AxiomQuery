# AxiomQuery

Specification-based query and aggregation engine for SQLAlchemy 2.0 ORM models.

Define filters as composable data — JSON lists, dicts, or Python AST nodes — and execute them against any ORM model without writing raw SQL.

---

## Install

```bash
pip install AxiomQuery
```

Requires Python 3.12+ and SQLAlchemy 2.0+.

---

## Quick start

```python
from axiom_query import QueryEngine

engine = QueryEngine(Order)   # inspect() once — no DB connection at construction

with Session(db) as session:
    # list
    records = engine.list(session, domain=[["status", "=", "CONFIRMED"]])

    # read_group
    groups, total = engine.read_group(
        session,
        groupby=["status"],
        aggregates=["__count", "total:sum"],
    )
```

---

## Domain filter syntax

A **domain** is a JSON-serialisable expression compiled to a WHERE clause at query time.

### Condition tuple

```python
[field_path, operator, value]
```

| Operator | Meaning |
|----------|---------|
| `=` `!=` `>` `<` `>=` `<=` | Comparison |
| `in` `not in` | Membership (value is a list) |
| `like` `ilike` | Pattern match (`%` wildcard) |
| `is_null` | Null check (value is `True`/`False`) |

### Logical composition

```python
# AND — list of conditions (implicit)
[["status", "=", "CONFIRMED"], ["total", ">", 100]]

# AND — explicit
{"and": [["status", "=", "CONFIRMED"], ["total", ">", 100]]}

# OR
{"or": [["status", "=", "DRAFT"], ["status", "=", "CANCELLED"]]}

# NOT
{"not": ["status", "=", "CANCELLED"]}

# Combined — list mixes plain conditions with logical dicts
[
    {"or": [["status", "=", "CONFIRMED"], ["status", "=", "DRAFT"]]},
    {"not": ["total", "=", 0]},
]
```

### Child field (EXISTS subquery)

Filter parent records by a child relationship field using dot notation. O2M relationships are automatically detected via `inspect()`.

```python
# Orders that have at least one line with quantity > 2
engine.list(session, domain=[["lines.quantity", ">", 2]])
```

---

## `list()` — filtered records

```python
records = engine.list(
    session,
    domain=None,          # domain expression or None (all records)
    limit=None,           # max records to return
    offset=None,          # records to skip
    order_by=None,        # [["field", "asc|desc"], ...]
)
# returns list[ORM model instances]
```

---

## `read_group()` — grouped aggregation

```python
groups, total = engine.read_group(
    session,
    groupby=["status", "created_at:month"],   # field or field:granularity
    aggregates=["__count", "total:sum"],       # __count or field:func
    domain=None,                              # WHERE filter
    having=None,                              # HAVING filter on aggregate aliases
    order_by=None,                            # [["alias", "asc|desc"], ...]
    limit=None,
    offset=None,
)
# returns (list[dict], int)  — each dict includes a __domain key
```

**Aggregate functions:** `count` `sum` `avg` `min` `max`

**Date granularities:** `day` `week` `month` `quarter` `year`

**Child aggregate** (LEFT JOIN):

```python
engine.read_group(session, groupby=["status"], aggregates=["lines.quantity:sum"])
```

**`__domain` drill-down** — each group result includes a `__domain` ready to pass back to `list()`:

```python
groups, _ = engine.read_group(session, groupby=["status"], aggregates=["__count"])
for group in groups:
    records = engine.list(session, domain=group["__domain"])
```

---

## Async API

Prefix any method with `a` and pass an `AsyncSession`:

```python
engine = QueryEngine(Order)

async with AsyncSession(db) as session:
    records = await engine.alist(session, domain=[["status", "=", "CONFIRMED"]])
    groups, total = await engine.aread_group(session, groupby=["status"], aggregates=["__count"])
```

---

## Schema derivation

`QueryEngine` derives its schema from `inspect(model_class)` at construction time — no separate descriptor needed:

- **Columns** → from `mapper.columns`
- **Child relations** → O2M relationships (`RelationshipDirection.ONETOMANY`) become filterable child entities
- **FK column** → resolved from `rel.synchronize_pairs`

---

## Error handling

Invalid field paths and unsupported operators raise `QueryError` before hitting the database:

```python
from axiom_query import QueryError

try:
    engine.list(session, domain=[["unknown_field", "=", "x"]])
except QueryError as e:
    print(e.code, e.message)   # INVALID_FILTER_FIELD  No field 'unknown_field' ...
```

---

## Examples

Self-contained runnable examples in [`examples/`](examples/):

```bash
python examples/example_sync.py
python examples/example_async.py
```

Both cover: simple filters, AND / OR / NOT, combined nesting, child EXISTS filtering, pagination, `read_group` with domain / date granularity / child aggregation / HAVING, and `__domain` drill-down.
