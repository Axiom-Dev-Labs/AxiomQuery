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

Here is an improved, livelier version of your acknowledgement note, complete with emojis and the added context about the Specification pattern acting as the core inspiration for the library. It is formatted directly for your `README.md`.

***

## 🙌 Acknowledgements & Inspirations

The creation of AxiomQuery was sparked by a desire to cleanly bridge pure domain logic with robust data access. The conceptual "trigger point" for this library came from **Martin Fowler and Eric Evans' Specification Pattern**—a brilliant blueprint for encapsulating business rules. However, it was the phenomenal foundation of **SQLAlchemy 2.0** that provided the mechanical reality, making it possible to seamlessly translate those decoupled domain specifications into highly optimized SQL. 

A huge thank you to the maintainers and contributors of SQLAlchemy. AxiomQuery is built explicitly as a specification-based query and aggregation engine for SQLAlchemy 2.0 ORM models, and it relies entirely on several of their most powerful features:

* 🔍 **Incredible Introspection (`inspect()`):** AxiomQuery automatically derives all necessary schema data—including `mapper.columns`, one-to-many relationships (`RelationshipDirection.ONETOMANY`), and foreign key synchronization pairs—directly from SQLAlchemy's introspection tools. This allows the engine to extract everything the compiler needs without ever forcing the developer to write duplicate descriptor code.
* 🏗️ **Robust Expression Language:** Our underlying AST compiler relies heavily on SQLAlchemy's composable query constructs. Mapping our 11 supported operators to native methods makes it incredibly easy to safely compile complex SQL `WHERE` clauses. It seamlessly handles advanced requirements, such as utilizing `EXISTS` subqueries for parent-child filtering and executing `LEFT JOIN` aggregations with database-specific date truncations.
* 🔌 **Decoupled Session Management:** Because SQLAlchemy cleanly separates the ORM models from the active database connection, AxiomQuery can operate as a thin, highly reusable facade. The library expects a caller-owned session (whether standard or an `AsyncSession`), allowing developers to easily manage transactions across multiple engines without friction.

Thank you for providing the introspection and query-building tools that make translating dynamic JSON expressions into complex SQL queries a reality! ✨

### 📚 References

* **The Specification Pattern:** [Specifications by Martin Fowler & Eric Evans (PDF)](https://martinfowler.com/apsupp/spec.pdf) - The foundational paper that inspired the core domain-driven architecture of this library.
* **SQLAlchemy 2.0:** [Official Documentation](https://docs.sqlalchemy.org/en/20/) - The robust ORM and toolkit that powers the AxiomQuery engine.