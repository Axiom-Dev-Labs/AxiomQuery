# Domain Filter Syntax

A **domain** is a JSON-serialisable expression that AxiomQuery compiles to a SQL `WHERE`
clause at query time. It is the argument you pass as `domain=...` to `list`, `search`,
`read_group`, and their async twins.

## Condition tuple

The leaf of every domain is a three-element condition:

```python
[field_path, operator, value]
```

```python
["status", "=", "CONFIRMED"]
["total", ">", 100]
["lines.quantity", ">=", 2]   # dot-notation crosses a relationship
```

`field_path` is a column name, optionally a dot-path across relationships (see
[Relational Filtering](relational-filtering.md)).

## Operators

AxiomQuery supports eleven operators (defined in `axiom_query.operators.Op`):

| Operator | Meaning | Value shape |
|----------|---------|-------------|
| `=` | Equals | scalar |
| `!=` | Not equals | scalar |
| `>` `<` `>=` `<=` | Comparison | scalar |
| `in` | Membership | list |
| `not in` | Non-membership | list |
| `like` | Case-sensitive pattern | string with `%` / `_` wildcards |
| `ilike` | Case-insensitive pattern | string with `%` / `_` wildcards |
| `is_null` | Null check | `True` (is null) / `False` (is not null) |

```python
["status", "in", ["DRAFT", "CANCELLED"]]
["product_name", "ilike", "%widget%"]
["customer_id", "is_null", False]        # orders that have a customer
```

!!! tip "String values are coerced to the column type"
    When a column is a `Date`/`DateTime`, a string value such as `"2026-01-15"` is parsed to
    the corresponding Python type automatically, so domains stay JSON-friendly.

## Logical composition

### Implicit AND — a list of conditions

A list of conditions is ANDed together:

```python
# status = CONFIRMED AND total >= 150
[
    ["status", "=", "CONFIRMED"],
    ["total", ">=", 150],
]
```

### Explicit `and` / `or` / `not` — a dict

Each logical dict has exactly **one** key. `and` and `or` take a list of **two or more**
items; `not` takes a single item.

```python
# AND (explicit)
{"and": [["status", "=", "CONFIRMED"], ["total", ">", 100]]}

# OR
{"or": [["status", "=", "DRAFT"], ["status", "=", "CANCELLED"]]}

# NOT
{"not": ["status", "=", "CANCELLED"]}
```

### Nesting and combining

Lists may mix plain conditions with logical dicts, and logical dicts may nest freely:

```python
# (status = CONFIRMED OR status = DRAFT) AND total >= 50 AND NOT total = 50
[
    {"or": [["status", "=", "CONFIRMED"], ["status", "=", "DRAFT"]]},
    ["total", ">=", 50],
    {"not": ["total", "=", 50]},
]

# (CONFIRMED AND total > 100) OR CANCELLED
{
    "or": [
        {"and": [["status", "=", "CONFIRMED"], ["total", ">", 100]]},
        ["status", "=", "CANCELLED"],
    ]
}
```

## Three input shapes

The same filter can be expressed three ways. All compile to the same AST and SQL.

=== "JSON list / dict"

    The serialisable form shown above — ideal for storing, sending over an API, or building
    from a UI.

    ```python
    engine.list(session, domain=[["status", "=", "CONFIRMED"], ["total", ">", 100]])
    ```

=== "Python AST nodes"

    Build the AST directly with the exported node types. They are immutable dataclasses that
    support the `&`, `|`, and `~` operators for composition:

    ```python
    from axiom_query import Condition, Op

    spec = (
        Condition("status", Op.EQ, "CONFIRMED")
        & Condition("total", Op.GT, 100)
    )
    # ~spec negates, spec_a | spec_b ORs
    ```

=== "parse_domain()"

    `parse_domain()` is the function that turns a JSON domain into the AST. It is exported so
    you can validate or inspect a domain without running a query:

    ```python
    from axiom_query import parse_domain

    spec = parse_domain([["status", "=", "CONFIRMED"]])
    ```

## Validation

Domains are validated before any SQL runs. A malformed structure, an unknown operator, or a
field that does not exist on the model raises `QueryError`:

```python
from axiom_query import QueryError

try:
    engine.list(session, domain=[["unknown_field", "=", "x"]])
except QueryError as e:
    print(e.code, e.message)   # INVALID_FILTER_FIELD  No field 'unknown_field' on Order ...
```

See [Relational Filtering](relational-filtering.md) for dot-path conditions and
[Aggregation & read_group](aggregation.md) for using domains as `read_group` filters.
