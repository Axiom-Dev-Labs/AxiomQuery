"""ModelSchema — derives table/column/child metadata from SA ORM models via inspect()."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import Column, Table
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import RelationshipDirection


@dataclass
class ChildSchema:
    name: str
    table: Table
    fk_field: str
    columns: dict[str, Column]


@dataclass
class ModelSchema:
    model_class: type
    table: Table
    columns: dict[str, Column]
    children: dict[str, ChildSchema] = field(default_factory=dict)


def derive_schema(model_class: type) -> ModelSchema:
    """Derive a ModelSchema from a SA ORM model class using inspect()."""
    mapper = sa_inspect(model_class)
    table = mapper.local_table
    columns = {col.key: col for col in mapper.columns}

    children: dict[str, ChildSchema] = {}
    for rel_name, rel in mapper.relationships.items():
        if rel.direction == RelationshipDirection.ONETOMANY:
            child_table = rel.mapper.local_table
            child_columns = {col.key: col for col in rel.mapper.columns}
            # Find the FK column on the child table via synchronize_pairs
            # synchronize_pairs: list of (parent_col, child_col) tuples
            _, child_fk_col = next(iter(rel.synchronize_pairs))
            fk_field = child_fk_col.key
            children[rel_name] = ChildSchema(
                name=rel_name,
                table=child_table,
                fk_field=fk_field,
                columns=child_columns,
            )

    return ModelSchema(
        model_class=model_class,
        table=table,
        columns=columns,
        children=children,
    )
