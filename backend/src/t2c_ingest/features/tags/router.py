from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.tags.service import jobs_count_by_tag
from t2c_ingest.models.tag import JobTag, Tag, slugify
from t2c_ingest.schemas.tag import TagCreate, TagOut, TagUpdate
from t2c_ingest.services.audit import record_audit

router = APIRouter(prefix="/tags", tags=["tags"])


def _out(db: Session, tag: Tag, counts: dict[int, int] | None = None) -> TagOut:
    out = TagOut.model_validate(tag)
    out.jobs_count = (counts or {}).get(tag.id, 0) if counts is not None else (
        db.scalar(select(func.count(JobTag.id)).where(JobTag.tag_id == tag.id)) or 0
    )
    return out


@router.get("", response_model=PageOut[TagOut])
def list_tags(
    params: PageParams = Depends(),
    search: str | None = None,
    active: bool | None = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_TAGS_READ)),
) -> PageOut[TagOut]:
    stmt = select(Tag)
    count_stmt = select(func.count(Tag.id))
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(Tag.name.ilike(like), Tag.slug.ilike(like)))
        count_stmt = count_stmt.where(or_(Tag.name.ilike(like), Tag.slug.ilike(like)))
    if active is not None:
        stmt = stmt.where(Tag.active.is_(active))
        count_stmt = count_stmt.where(Tag.active.is_(active))
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Tag.name).offset(params.offset).limit(params.limit)).all()
    counts = jobs_count_by_tag(db, [t.id for t in rows])
    return PageOut.build([_out(db, t, counts) for t in rows], total, params)


@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: TagCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_TAGS_WRITE)),
) -> TagOut:
    tag = Tag(name=payload.name.strip(), slug=slugify(payload.name), description=payload.description,
              color=payload.color, active=payload.active, created_by=user.id, updated_by=user.id)
    db.add(tag)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Já existe uma tag com esse slug.")
    record_audit(db, action="TAG_CREATED", user=user, entity_type="tag", entity_id=tag.id, detail={"slug": tag.slug})
    db.commit()
    db.refresh(tag)
    return _out(db, tag)


@router.get("/{tag_id}", response_model=TagOut)
def get_tag(tag_id: int, db: Session = Depends(get_db), _: CurrentUser = Depends(require_permission(perms.INGEST_TAGS_READ))) -> TagOut:
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag não encontrada")
    return _out(db, tag)


@router.put("/{tag_id}", response_model=TagOut)
def update_tag(
    tag_id: int, payload: TagUpdate,
    db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission(perms.INGEST_TAGS_WRITE)),
) -> TagOut:
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag não encontrada")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"]:
        tag.name = data["name"].strip()
        tag.slug = slugify(data["name"])
    for k in ("description", "color", "active"):
        if k in data:
            setattr(tag, k, data[k])
    tag.updated_by = user.id
    tag.updated_at = datetime.now(timezone.utc)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug já existe.")
    record_audit(db, action="TAG_UPDATED", user=user, entity_type="tag", entity_id=tag.id)
    db.commit()
    db.refresh(tag)
    return _out(db, tag)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission(perms.INGEST_TAGS_DELETE))) -> None:
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag não encontrada")
    in_use = db.scalar(select(func.count(JobTag.id)).where(JobTag.tag_id == tag_id)) or 0
    if in_use:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Tag em uso por {in_use} job(s); remova os vínculos antes.")
    record_audit(db, action="TAG_DELETED", user=user, entity_type="tag", entity_id=tag.id, detail={"slug": tag.slug})
    db.delete(tag)
    db.commit()


@router.post("/{tag_id}/activate", response_model=TagOut)
def activate_tag(tag_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission(perms.INGEST_TAGS_WRITE))) -> TagOut:
    return _toggle(db, tag_id, True, user)


@router.post("/{tag_id}/deactivate", response_model=TagOut)
def deactivate_tag(tag_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission(perms.INGEST_TAGS_WRITE))) -> TagOut:
    return _toggle(db, tag_id, False, user)


def _toggle(db: Session, tag_id: int, active: bool, user: CurrentUser) -> TagOut:
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag não encontrada")
    tag.active = active
    tag.updated_by = user.id
    tag.updated_at = datetime.now(timezone.utc)
    record_audit(db, action="TAG_ACTIVATED" if active else "TAG_DEACTIVATED", user=user, entity_type="tag", entity_id=tag.id)
    db.commit()
    db.refresh(tag)
    return _out(db, tag)
