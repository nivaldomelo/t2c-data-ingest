from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Text, func, or_, select
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.models.audit import AuditEvent
from t2c_ingest.schemas.audit import AuditActionCount, AuditEventOut, AuditSummary

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/summary", response_model=AuditSummary)
def summary(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_ADMIN)),
) -> AuditSummary:
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)
    total = db.scalar(select(func.count(AuditEvent.id))) or 0
    today = db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.created_at >= day_ago)) or 0
    last_7d = db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.created_at >= week_ago)) or 0
    distinct_users = db.scalar(
        select(func.count(func.distinct(AuditEvent.user_email))).where(AuditEvent.created_at >= week_ago, AuditEvent.user_email.is_not(None))
    ) or 0
    top = db.execute(
        select(AuditEvent.action, func.count(AuditEvent.id).label("c"))
        .where(AuditEvent.created_at >= week_ago).group_by(AuditEvent.action).order_by(func.count(AuditEvent.id).desc()).limit(8)
    ).all()
    return AuditSummary(
        total=total, today=today, last_7d=last_7d, distinct_users_7d=distinct_users,
        top_actions=[AuditActionCount(action=a, count=c) for a, c in top],
    )


@router.get("/actions", response_model=list[str])
def actions(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_ADMIN)),
) -> list[str]:
    rows = db.scalars(select(AuditEvent.action).distinct().order_by(AuditEvent.action)).all()
    return list(rows)


@router.get("/events", response_model=PageOut[AuditEventOut])
def events(
    params: PageParams = Depends(),
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    user_email: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_ADMIN)),
) -> PageOut[AuditEventOut]:
    stmt = select(AuditEvent)
    count_stmt = select(func.count(AuditEvent.id))
    filters = []
    if action:
        filters.append(AuditEvent.action == action)
    if entity_type:
        filters.append(AuditEvent.entity_type == entity_type)
    if entity_id:
        filters.append(AuditEvent.entity_id == entity_id)
    if user_email:
        filters.append(AuditEvent.user_email.ilike(f"%{user_email.strip()}%"))
    if date_from:
        filters.append(AuditEvent.created_at >= date_from)
    if date_to:
        filters.append(AuditEvent.created_at <= date_to)
    if search:
        like = f"%{search.strip()}%"
        filters.append(or_(
            AuditEvent.action.ilike(like), AuditEvent.entity_type.ilike(like),
            AuditEvent.user_email.ilike(like), func.cast(AuditEvent.detail, Text).ilike(like),
        ))
    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(AuditEvent.id.desc()).offset(params.offset).limit(params.limit)).all()
    return PageOut.build([AuditEventOut.model_validate(r) for r in rows], total, params)
