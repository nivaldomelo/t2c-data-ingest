from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from t2c_ingest.models.variable import VARIABLE_SCOPES, VARIABLE_TYPES


class VariableBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    variable_type: str = "string"
    scope: str = "global"
    environment: str | None = None
    is_secret: bool = False
    active: bool = True

    @field_validator("variable_type")
    @classmethod
    def _vt(cls, v: str) -> str:
        if v not in VARIABLE_TYPES:
            raise ValueError(f"variable_type deve ser um de {VARIABLE_TYPES}")
        return v

    @field_validator("scope")
    @classmethod
    def _sc(cls, v: str) -> str:
        if v not in VARIABLE_SCOPES:
            raise ValueError(f"scope deve ser um de {VARIABLE_SCOPES}")
        return v


class VariableCreate(VariableBase):
    value: str | None = None


class VariableUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    # Omitted/empty value keeps the current one (important for secrets).
    value: str | None = None
    variable_type: str | None = None
    scope: str | None = None
    environment: str | None = None
    is_secret: bool | None = None
    active: bool | None = None


class VariableOut(VariableBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # Plaintext value for non-secrets; None for secrets (see masked_value).
    value: str | None = None
    masked_value: str | None = None
    has_value: bool = False
    created_by: int | None = None
    updated_by: int | None = None
    created_at: datetime
    updated_at: datetime | None = None


class VariableUsage(BaseModel):
    python: str
    spark: str


class VariableDetailOut(VariableOut):
    usage: VariableUsage


class VariableSummary(BaseModel):
    total: int
    active: int
    secret: int
    global_scope: int
    with_environment: int
