import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from t2c_ingest.core.config import settings

logger = logging.getLogger(__name__)

engine_kwargs = {
    "future": True,
    "pool_pre_ping": True,
    "pool_recycle": 1800,
    "echo": False,
}

try:
    parsed_url = make_url(settings.database_url)
    if parsed_url.drivername.startswith("postgresql"):
        # Search the ingest schema first, then the t2c_data reference schema (users/roles),
        # then public. Cross-schema reads of t2c_data tables resolve without qualification.
        engine_kwargs["connect_args"] = {
            "options": f"-csearch_path={settings.db_schema},{settings.reference_schema},public",
            "connect_timeout": 10,
        }
except Exception:  # noqa: BLE001 - never block startup on URL introspection
    pass

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
