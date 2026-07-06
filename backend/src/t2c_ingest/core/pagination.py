from __future__ import annotations

from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

T = TypeVar("T")

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 200


class PageParams:
    """Standard list pagination params (25 items/page, mirroring t2c_data)."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="1-based page number"),
        page_size: int = Query(
            DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"
        ),
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class PageOut(BaseModel, Generic[T]):
    page: int
    page_size: int
    total: int
    total_pages: int = 0
    has_more: bool = False
    items: list[T] = Field(default_factory=list)

    @classmethod
    def build(cls, items: list[T], total: int, params: PageParams) -> "PageOut[T]":
        total_pages = (total + params.page_size - 1) // params.page_size if params.page_size else 0
        return cls(
            page=params.page,
            page_size=params.page_size,
            total=total,
            total_pages=total_pages,
            has_more=params.page < total_pages,
            items=items,
        )
