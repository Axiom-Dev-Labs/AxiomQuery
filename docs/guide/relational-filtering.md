# Relational Filtering

AxiomQuery filters and groups across relationships using **dot-notation** in the field path —
no joins to write, no relationship names to register. Relationships are discovered
automatically from `inspect()` when the engine is constructed.

```python
["customer.name", "=", "Joy"]          # filter by a Many-to-One field
["lines.quantity", ">", 2]             # filter by a One-to-Many field
["customer.city.country.name", "ilike", "%Ind%"]   # N-level deep
```

The **last** segment is always a scalar column; every segment before it is a relationship to
traverse.

## How it compiles

Every relational hop is compiled as a **correlated `EXISTS` subquery**. This holds for both
relationship directions and for chains of arbitrary depth, mixing directions freely:

- **Many-to-One (M2O)** — the foreign key lives on the current table. AxiomQuery correlates
  the referenced table's primary key to the local FK.

  ```python
  # orders whose customer is named Joy
  engine.list(session, domain=[["customer.name", "=", "Joy"]])
  ```

- **One-to-Many (O2M)** — the foreign key lives on the child table. AxiomQuery correlates the
  child rows back to the parent's primary key.

  ```python
  # orders that have at least one line with quantity > 2
  engine.list(session, domain=[["lines.quantity", ">", 2]])
  ```

Because each hop is an `EXISTS`, an O2M condition means "**has at least one** related row
matching" — it does not multiply parent rows the way a plain join would.

## N-level deep paths

Chain as many relationships as you need. Each segment adds one correlated `EXISTS`, nested
inside the previous one, so M2O and O2M can be combined in a single path:

```python
# 2-level M2O: order → customer → city
engine.list(session, domain=[["customer.city.name", "=", "Mumbai"]])

# 3-level M2O: order → customer → city → country
engine.list(session, domain=[["customer.city.country.name", "ilike", "%Ind%"]])

# O2M then M2O: order → lines → product
engine.list(session, domain=[["lines.product.category", "=", "Electronics"]])
```

## Combining with other conditions

Relational conditions are ordinary conditions — combine them with scalar conditions and
logical operators just like any other:

```python
engine.list(
    session,
    domain=[
        ["status", "=", "CONFIRMED"],
        ["lines.quantity", ">", 2],
        {"not": ["customer.name", "=", "Bob"]},
    ],
)
```

## In `read_group`

Dot-notation also works in `read_group` — both as a child aggregate target and as a deep
`groupby` path. See [Aggregation & read_group](aggregation.md#child-aggregates):

```python
# group orders by their lines' product category, summing line quantity
engine.read_group(
    session,
    groupby=["lines.product.category"],
    aggregates=["lines.quantity:sum"],
)
```

## Validation

An unknown relationship or a missing field on a related model raises `QueryError` before any
SQL runs, with the available relations listed in the message:

```text
INVALID_FILTER_FIELD  No relation 'custmer' on Order. Available: customer, lines
```
