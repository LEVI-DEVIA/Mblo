"""Idempotent writes: every insert is an upsert keyed on the natural unique constraint."""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from mblo.db import models as m


def upsert(session: Session, table, rows: list[dict], conflict: list[str], exclude_update: Iterable[str] = ()) -> int:
    if not rows:
        return 0
    stmt = insert(table).values(rows)
    skip = set(conflict) | set(exclude_update) | {"id"}
    update_cols = {c: getattr(stmt.excluded, c) for c in rows[0].keys() if c not in skip}
    if update_cols:
        stmt = stmt.on_conflict_do_update(index_elements=conflict, set_=update_cols)
    else:
        stmt = stmt.on_conflict_do_nothing(index_elements=conflict)
    session.execute(stmt)
    return len(rows)


def company_ids(session: Session) -> dict[str, int]:
    return {t: i for t, i in session.execute(select(m.Company.ticker, m.Company.id)).all()}


def ensure_companies(session: Session, rows: list[dict], exclude_update: Iterable[str] = ()) -> dict[str, int]:
    """rows: [{ticker, name, ...optional fields}]. Returns ticker -> id."""
    upsert(session, m.Company, rows, conflict=["ticker"], exclude_update=exclude_update)
    session.flush()
    return company_ids(session)
