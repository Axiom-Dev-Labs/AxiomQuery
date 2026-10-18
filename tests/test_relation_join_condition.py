"""Relation paths use the relationship's full join condition, not just its foreign key."""

from __future__ import annotations

import pytest
from sqlalchemy import String, and_, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, foreign, mapped_column, relationship

from axiom_query.engine import QueryEngine


class Base(DeclarativeBase):
    pass


class Message(Base):
    """Points to any record by model name + id (no real foreign key)."""
    __tablename__ = "message"
    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str] = mapped_column(String(20))
    res_id: Mapped[int]
    body: Mapped[str] = mapped_column(String(50))


class Ticket(Base):
    __tablename__ = "ticket"
    id: Mapped[int] = mapped_column(primary_key=True)
    messages: Mapped[list[Message]] = relationship(viewonly=True, primaryjoin=lambda: and_(
        Message.model == "ticket", foreign(Message.res_id) == Ticket.id))


class Invoice(Base):
    __tablename__ = "invoice"
    id: Mapped[int] = mapped_column(primary_key=True)


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as sess:
        sess.add_all([
            Ticket(id=1), Ticket(id=2), Invoice(id=1),
            Message(model="invoice", res_id=1, body="paid"),   # invoice 1, not ticket 1
            Message(model="ticket", res_id=2, body="urgent"),
        ])
        sess.commit()
        yield sess


def test_extra_join_condition_is_applied(session):
    engine = QueryEngine(Ticket)
    assert engine.list(session, domain=[["messages.body", "=", "paid"]]) == []
    assert [t.id for t in engine.list(session, domain=[["messages.body", "=", "urgent"]])] == [2]


def test_count_uses_the_full_join_condition(session):
    assert QueryEngine(Ticket).count(session, domain=[["messages.body", "=", "paid"]]) == 0


def test_read_group_joins_use_the_full_join_condition(session):
    groups, _ = QueryEngine(Ticket).read_group(session, groupby=["messages.body"], aggregates=["__count"])
    # ticket 1 has no messages of its own; the invoice's "paid" message must not be joined to it
    assert {g["messages__body"]: g["__count"] for g in groups} == {None: 1, "urgent": 1}
