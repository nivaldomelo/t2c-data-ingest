from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from t2c_ingest.core.config import settings


class Base(DeclarativeBase):
    """Declarative base bound to the ingest schema (default ``t2c_data_ingest``)."""

    metadata = MetaData(schema=settings.db_schema)
