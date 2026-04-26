# Changelog

All notable changes to `AxiomQuery` are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.0] — 2026-04-26

### Added

- `search()` / `asearch()` — streaming iteration over large result sets via SQLAlchemy server-side cursors with `yield_per=1000`
  - Sync `search()` returns a Python iterator (consume with `for`); async `asearch()` returns an `AsyncScalarResult` (consume with `async for`)
  - Single-pass; no `limit` / `offset` (use `list()` / `alist()` for paginated/materialised access)
- `DEFAULT_PREFETCH = 1000` module-level constant in `engine.py`
- Internal `_build_stmt()` helper consolidating the `select + where + order_by + limit + offset` block shared by `list` / `alist` / `search` / `asearch` / `read_group`

### Changed

- `list()` / `alist()` continue to return a materialised `list` — behaviour and signature unchanged from 0.2.0 callers' perspective

---

## [0.2.0] — 2026-04-13

### Added

- M2O (Many-to-One) relational field filtering via dot-notation (e.g. `["customer.name", "ilike", "%Alice%"]`)
  - Generates an `EXISTS` subquery joining the referenced table on the local FK column
  - Composes freely with scalar filters and O2M child filters in the same domain
- `RelatedSchema` dataclass in `schema.py` to capture M2O relationship metadata (referenced table, local FK column, columns)
- `related` field on `ModelSchema` mapping relationship attribute names to their `RelatedSchema`

---

## [0.1.1] — 2026-04-05
Acknowledgement and Inspiration Added

### Added
- updated the README.md file with details

## [0.1.0] — 2026-03-29

Initial release.

### Added

- `QueryEngine` — specification-based query facade for any SQLAlchemy 2.0 ORM model
- `list()` / `alist()` — filtered record retrieval with `limit`, `offset`, `order_by`
- `read_group()` / `aread_group()` — grouped aggregation (GROUP BY + HAVING) with `__domain` drill-down per group
- Domain filter DSL — composable JSON expressions: `[field, op, value]`, `{"and": [...]}`, `{"or": [...]}`, `{"not": ...}`
- Full operator set: `=` `!=` `>` `<` `>=` `<=` `in` `not in` `like` `ilike` `is_null`
- Child field filtering via EXISTS subquery (dot notation: `"lines.quantity"`)
- Child field aggregation via LEFT JOIN (`"lines.quantity:sum"`)
- Date granularity grouping: `day` `week` `month` `quarter` `year`
- Aggregate functions: `count` `sum` `avg` `min` `max`
- HAVING filter on aggregate aliases
- Schema auto-derived from `inspect(model_class)` — O2M relationships are children by convention
- Sync (`Session`) and async (`AsyncSession`) APIs
- `QueryError` with `code` and `message` — field validation at compile time, before DB
- `py.typed` marker — PEP 561 inline type annotations
