# Changelog

All notable changes to `AxiomQuery` are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
