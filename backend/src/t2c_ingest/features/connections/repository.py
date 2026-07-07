from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from t2c_ingest.models.connection import Connection


def get_connection_by_ref(db: Session, ref: str | int) -> Connection | None:
    """Resolve a connection by numeric id or by unique name.

    Lets jobs reference connections either by id (e.g. 3) or by name (e.g. "mysql_1").
    """
    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
        conn = db.get(Connection, int(ref))
        if conn:
            return conn
    return db.scalar(select(Connection).where(Connection.name == str(ref)))
