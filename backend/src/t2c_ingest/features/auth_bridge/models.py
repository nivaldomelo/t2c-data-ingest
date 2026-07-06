from __future__ import annotations

from sqlalchemy import Boolean, Column, ForeignKey, Integer, MetaData, String, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from t2c_ingest.core.config import settings

# A SEPARATE metadata/base bound to the t2c_data reference schema. These tables are OWNED by
# t2c_data — they are mapped read-only here and are intentionally excluded from the ingest
# Alembic autogenerate (different metadata + different schema).
reference_metadata = MetaData(schema=settings.reference_schema)


class ReferenceBase(DeclarativeBase):
    metadata = reference_metadata


user_role = Table(
    "user_role",
    ReferenceBase.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    ReferenceBase.metadata,
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id"), primary_key=True),
)


class ReferenceUser(ReferenceBase):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255))
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    roles: Mapped[list["ReferenceRole"]] = relationship(
        "ReferenceRole", secondary=user_role, lazy="selectin"
    )


class ReferenceRole(ReferenceBase):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))

    permissions: Mapped[list["ReferencePermission"]] = relationship(
        "ReferencePermission", secondary=role_permissions, lazy="selectin"
    )


class ReferencePermission(ReferenceBase):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
