# Aggregation & read_group

`read_group` runs grouped aggregation — the analytical counterpart to `list`. Its shape is
modelled on Odoo's `read_group` (see [Philosophy](../philosophy.md#inspired-by-odoo)).

## Signature

```python
groups, total = engine.read_group(
    session,
    groupby=["status", "created_at:month"],   # field or field:granularity
    aggregates=["__count", "total:sum"],       # __count or field:func
    domain=None,                              # WHERE filter (a normal domain)
    having=None,                              # filter on aggregate aliases
    order_by=None,                            # [["alias", "asc|desc"], ...]
    limit=None,
    offset=None,
)
```

It returns a tuple `(groups, total)`:

- `groups` — a `list[dict]`. Each dict is keyed by the **groupby aliases**, the **aggregate
  aliases**, plus a `__domain` key (see drill-down below).
- `total` — the number of groups returned.

## Grouping

`groupby` accepts plain field names and, for date/datetime columns, a `field:granularity`
form that buckets by a truncated date:

```python
engine.read_group(session, groupby=["status"], aggregates=["__count"])
engine.read_group(session, groupby=["created_at:month"], aggregates=["__count"])
```

**Date granularities:** `day` · `week` · `month` · `quarter` · `year`

A bucketed group is aliased with a double underscore, e.g. `created_at:month` →
`created_at__month`. Use that alias in `order_by`:

```python
groups, _ = engine.read_group(
    session,
    groupby=["created_at:month"],
    aggregates=["__count", "total:sum"],
    order_by=[["created_at__month", "asc"]],
)
```

## Aggregates

Each entry in `aggregates` is either the special `__count` (row count) or a
`field:func` pair:

```python
aggregates=["__count", "total:sum", "total:avg"]
```

**Aggregate functions:** `count` · `sum` · `avg` · `min` · `max`

A `field:func` aggregate is aliased as `field__func` (e.g. `total:sum` → `total__sum`).

## HAVING

`having` filters on the aggregate/groupby aliases *after* grouping. It uses the same domain
structure as `domain`, but referencing aliases instead of columns:

```python
# only groups with more than one row
engine.read_group(
    session,
    groupby=["status"],
    aggregates=["__count"],
    having=[["__count", ">", 1]],
)

# groups whose summed total exceeds 100
engine.read_group(
    session,
    groupby=["status"],
    aggregates=["total:sum"],
    having=[["total__sum", ">", 100]],
)
```

!!! note
    `HAVING` supports comparison operators and `in` / `not in`. Pattern operators
    (`like` / `ilike`) and `is_null` are not valid in a `HAVING` clause.

## Child aggregates

Aggregate over a related collection with dot-notation. AxiomQuery resolves the relationship
and aggregates the child column (compiled as a `LEFT JOIN` so groups with no children still
appear):

```python
# sum of all line quantities per order status
engine.read_group(
    session,
    groupby=["status"],
    aggregates=["__count", "lines.quantity:sum"],
)
```

You can also group by a deep relational path — see
[Relational Filtering](relational-filtering.md):

```python
engine.read_group(
    session,
    groupby=["lines.product.category"],
    aggregates=["lines.quantity:sum"],
)
```

## `__domain` drill-down

Every group result carries a `__domain` — a ready-made domain that selects exactly the
records in that group. Feed it straight back into `list()` to drill from a summary row to its
underlying records:

```python
groups, _ = engine.read_group(session, groupby=["status"], aggregates=["__count"])

for group in groups:
    records = engine.list(session, domain=group["__domain"])
    print(group["status"], group["__count"], "→", len(records), "records")
```

If you passed a `domain` to `read_group`, it is combined into each group's `__domain`, so the
drill-down stays consistent with the original filter.

## Async

Use `aread_group` with an `AsyncSession` — identical arguments and return shape. See
[Async Usage](async.md).
