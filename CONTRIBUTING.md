# Contributing to AxiomQuery

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Axiom-Dev-Labs/AxiomQuery
cd AxiomQuery
uv sync
```

## Running tests

```bash
uv run pytest
```

The test suite uses SQLite in-memory — no external DB needed.

## Project layout

```
src/axiom_query/
  errors.py             QueryError
  operators.py          Op enum
  ast.py                Immutable AST nodes (Condition, And, Or, Not, Bool)
  parser.py             parse_domain() — JSON → AST
  schema.py             derive_schema() — ModelSchema from SA inspect()
  compiler.py           compile_domain() → SA WHERE ColumnElement
  aggregation.py        ReadGroupQuery AST nodes
  aggregation_parser.py parse_read_group() — raw dict → ReadGroupQuery
  compiler_aggregate.py compile_read_group() → SA SELECT
  engine.py             QueryEngine — public facade
tests/
  conftest.py           Order/OrderLine fixtures, SQLite engine
  test_list.py          list() / alist() tests
  test_read_group.py    read_group() tests
  test_async.py         async tests
examples/
  example_sync.py       Runnable sync walkthrough
  example_async.py      Runnable async walkthrough
```

## Adding a new operator

1. Add the value to `Op` in `operators.py`
2. Handle it in `_apply_operator()` in `compiler.py`
3. Handle it in `_apply_having_operator()` if valid in HAVING context
4. Add a test in `test_list.py`

## Adding a new aggregate function

1. Add the value to `AggFunc` in `aggregation.py`
2. Handle it in `_compile_aggregate_column()` in `compiler_aggregate.py`
3. Add a test in `test_read_group.py`

## Release checklist

- [ ] Bump `version` in `pyproject.toml` and `__init__.py`
- [ ] Add entry to `CHANGELOG.md`
- [ ] Run full test suite: `uv run pytest`
- [ ] Build: `uv build`
- [ ] Publish: `uv publish`
