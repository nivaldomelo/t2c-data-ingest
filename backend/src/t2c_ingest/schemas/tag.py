from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TagLite(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    color: str | None = None


class TagBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = None
    color: str | None = None
    active: bool = True


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    active: bool | None = None


class TagOut(TagBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    jobs_count: int = 0
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime | None = None


class JobTagsUpdate(BaseModel):
    tags: list[str] = Field(default_factory=list)
