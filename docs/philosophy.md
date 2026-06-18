# Philosophy

AxiomQuery exists to bridge **pure domain logic** and **robust data access**: to let you
express *what* to select as plain, portable data, and leave *how* to fetch it to a
dialect-aware compiler.

## Specifications as data

A filter is a value, not code. A *domain* is a JSON-serialisable expression you can store in
a column, send over an API, persist as a saved view, or build from a UI — then execute
unchanged. This is the [Specification pattern](https://martinfowler.com/apsupp/spec.pdf) of
Fowler and Evans, reframed for the data layer: business rules are encapsulated, composable
objects (`And`, `Or`, `Not`, `Condition`) that combine with `&`, `|`, and `~`.

## Intent vs. execution

AxiomQuery keeps a clean seam between intent and execution:

```
domain (data) → parse_domain → AST (QuerySpec) → compile → dialect-aware SQL
```

The domain captures intent. The compiler turns it into SQLAlchemy expressions, picking the
right strategy per case — correlated `EXISTS` for relational paths, `LEFT JOIN` for child
aggregates, database-specific date truncation for grouping. You never write the SQL, and the
same domain runs against any backend SQLAlchemy supports.

## Design goals

- **Standalone** — a thin facade over any SQLAlchemy 2.0 model; no framework, no base class
  to inherit.
- **Zero-config schema** — everything is derived from `inspect(model_class)` at construction:
  columns, relationships, and foreign keys. No duplicate descriptor to maintain.
- **No connection at construction** — `QueryEngine(Model)` is pure introspection. Sessions
  are caller-owned and passed per call, sync or async.
- **Typed** — ships with `py.typed`.
- **Fail fast** — invalid fields, operators, and structures raise `QueryError` *before* a
  query reaches the database.

## Inspired by Odoo

AxiomQuery's filter language borrows the ergonomics of **Odoo's ORM *domain*** — a list of
`[field, operator, value]` criteria that read as data, with implicit `AND` between them — and
the shape of its **`read_group`** grouped-aggregation API. We keep the parts that make Odoo
domains pleasant and adapt the rest to plain SQLAlchemy 2.0.

| Odoo | AxiomQuery |
|------|-----------|
| `[('state', '=', 'done')]` triple domain | `[["status", "=", "CONFIRMED"]]` |
| Implicit `AND` between criteria | Implicit `AND` in a list |
| Polish-prefix `'&'`, `'|'`, `'!'` operators | Explicit `{"and" / "or" / "not": ...}` dicts |
| Dot-notation related fields (`partner_id.country_id.name`) | Dot-notation relational paths (correlated `EXISTS`) |
| `read_group(domain, fields, groupby)` | `read_group(groupby, aggregates, domain)` |

**What differs:** AxiomQuery is a standalone engine over any SQLAlchemy model (no Odoo ORM),
domains are JSON-serialisable, and boolean logic uses readable `and` / `or` / `not` dicts
(or Python `&` / `|` / `~`) instead of prefix operators.

## References

- **The Specification Pattern** — [Specifications, Fowler & Evans (PDF)](https://martinfowler.com/apsupp/spec.pdf)
- **SQLAlchemy 2.0** — [Official documentation](https://docs.sqlalchemy.org/en/20/)
- **Odoo ORM domains** — [Search domains reference](https://www.odoo.com/documentation/latest/developer/reference/backend/orm.html#search-domains)
