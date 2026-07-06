from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from t2c_ingest.core.config import settings
from t2c_ingest.models import Base  # noqa: F401  (registers all ingest models)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def _include_object(object_, name, type_, reflected, compare_to):
    """Only manage objects in the ingest schema. The t2c_data reference tables
    (users/roles/permissions) live in another schema and must never be touched."""
    desired_schema = settings.db_schema or "public"
    schema = None
    if type_ == "table":
        schema = getattr(object_, "schema", None)
    elif type_ in {"index", "unique_constraint", "foreign_key_constraint", "primary_key_constraint"}:
        table = getattr(object_, "table", None)
        schema = getattr(table, "schema", None) if table is not None else None
    if schema is None:
        schema = desired_schema
    return schema == desired_schema


def _include_name(name, type_, parent_names):
    desired_schema = settings.db_schema or "public"
    if type_ == "schema":
        return name == desired_schema
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    desired_schema = settings.db_schema or "public"
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        include_name=_include_name,
        include_object=_include_object,
        version_table_schema=desired_schema,
        compare_type=True,
    )
    with context.begin_transaction():
        context.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{desired_schema}"'))
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    desired_schema = settings.db_schema or "public"
    with connectable.connect() as connection:
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{desired_schema}"'))
        connection.execute(text(f'SET search_path TO "{desired_schema}", public'))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=_include_name,
            include_object=_include_object,
            version_table_schema=desired_schema,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
