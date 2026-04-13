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
class RelatedSchema:
    """Represents a Many-to-One (M2O) relationship on the inspected model.

    The FK column lives on the *current* table (e.g. orders.customer_id),
    and the referenced table holds the PK that FK points to.
    """

    name: str
    table: Table
    fk_field: str  # FK column name on the current (owning) table
    columns: dict[str, Column]


@dataclass
class ModelSchema:
    model_class: type
    table: Table
    columns: dict[str, Column]
    children: dict[str, ChildSchema] = field(default_factory=dict)
    related: dict[str, RelatedSchema] = field(default_factory=dict)


def derive_schema(model_class: type) -> ModelSchema:
    """Derive a ModelSchema from a SA ORM model class using inspect()."""
    mapper = sa_inspect(model_class)
    table = mapper.local_table
    columns = {col.key: col for col in mapper.columns}

    children: dict[str, ChildSchema] = {}
    related: dict[str, RelatedSchema] = {}
    for rel_name, rel in mapper.relationships.items():
        if rel.direction == RelationshipDirection.ONETOMANY:
            child_table = rel.mapper.local_table
            child_columns = {col.key: col for col in rel.mapper.columns}
            # synchronize_pairs: list of (parent_col, child_col) tuples
            _, child_fk_col = next(iter(rel.synchronize_pairs))
            children[rel_name] = ChildSchema(
                name=rel_name,
                table=child_table,
                fk_field=child_fk_col.key,
                columns=child_columns,
            )
        elif rel.direction == RelationshipDirection.MANYTOONE:
            ref_table = rel.mapper.local_table
            ref_columns = {col.key: col for col in rel.mapper.columns}
            # synchronize_pairs for M2O: (referenced_pk_col, local_fk_col)
            _, local_fk_col = next(iter(rel.synchronize_pairs))
            related[rel_name] = RelatedSchema(
                name=rel_name,
                table=ref_table,
                fk_field=local_fk_col.key,
                columns=ref_columns,
            )

    return ModelSchema(
        model_class=model_class,
        table=table,
        columns=columns,
        children=children,
        related=related,
    )
