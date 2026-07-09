"""Admin-managed access to the ingest tool.

Access is opt-in: admins (t2c_data admin roles) always have full access; every other user must
be explicitly granted access here, which gives them READ-ONLY use of the tool. This router lets
an admin search existing t2c_data users and grant/revoke that access.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge.models import ReferenceUser
from t2c_ingest.features.auth_bridge.permissions import ADMIN_ROLE_NAMES
from t2c_ingest.features.access.schemas import AccessSummary, AccessUserOut, GrantIn, GrantOut
from t2c_ingest.models.access import IngestUserAccess
from t2c_ingest.services.audit import record_audit

router = APIRouter(prefix="/access", tags=["access"])


def _norm(email: str) -> str:
    return (email or "").strip().lower()


def _granted_emails(db: Session) -> set[str]:
    rows = db.scalars(select(IngestUserAccess.email).where(IngestUserAccess.active.is_(True))).all()
    return {e.lower() for e in rows}


@router.get("/summary", response_model=AccessSummary)
def summary(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_ADMIN)),
) -> AccessSummary:
    users = db.scalars(select(ReferenceUser)).all()
    admins = sum(1 for u in users if {r.name for r in u.roles} & ADMIN_ROLE_NAMES)
    granted = db.scalar(select(func.count(IngestUserAccess.id)).where(IngestUserAccess.active.is_(True))) or 0
    return AccessSummary(admins=admins, granted=int(granted), total_users=len(users))


@router.get("/users", response_model=list[AccessUserOut])
def search_users(
    q: str | None = Query(None, description="Busca por e-mail ou nome"),
    only_without_access: bool = False,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_ADMIN)),
) -> list[AccessUserOut]:
    """Search t2c_data users, annotated with their ingest access status."""
    stmt = select(ReferenceUser)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(ReferenceUser.email.ilike(like), ReferenceUser.name.ilike(like), ReferenceUser.full_name.ilike(like)))
    users = db.scalars(stmt.order_by(ReferenceUser.email).limit(100)).all()
    granted = _granted_emails(db)
    out: list[AccessUserOut] = []
    for u in users:
        roles = sorted({r.name for r in u.roles})
        is_admin = bool(set(roles) & ADMIN_ROLE_NAMES)
        has_access = is_admin or (u.email.lower() in granted)
        if only_without_access and has_access:
            continue
        out.append(AccessUserOut(
            email=u.email, name=u.name or u.full_name, roles=roles,
            is_active=bool(u.is_active), is_admin=is_admin, has_access=has_access,
        ))
    return out


@router.get("", response_model=list[GrantOut])
def list_grants(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_ADMIN)),
) -> list[GrantOut]:
    rows = db.scalars(select(IngestUserAccess).order_by(IngestUserAccess.email)).all()
    return [GrantOut.model_validate(r) for r in rows]


@router.post("", response_model=GrantOut, status_code=status.HTTP_201_CREATED)
def grant_access(
    payload: GrantIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_ADMIN)),
) -> GrantOut:
    email = _norm(payload.email)
    if not email:
        raise HTTPException(status_code=422, detail="E-mail obrigatório.")
    ref = db.scalar(select(ReferenceUser).where(func.lower(ReferenceUser.email) == email))
    if not ref:
        raise HTTPException(status_code=404, detail="Usuário não encontrado no t2c_data.")

    row = db.scalar(select(IngestUserAccess).where(func.lower(IngestUserAccess.email) == email))
    if row:
        row.active = True
        row.note = payload.note
        row.granted_by = user.email
    else:
        row = IngestUserAccess(email=ref.email.lower(), note=payload.note, active=True, granted_by=user.email)
        db.add(row)
    db.flush()
    record_audit(db, action="ingest.access.granted", user=user, entity_type="user_access",
                 entity_id=email, detail={"email": email})
    db.commit()
    db.refresh(row)
    return GrantOut.model_validate(row)


@router.delete("/{email}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_access(
    email: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_ADMIN)),
) -> None:
    norm = _norm(email)
    row = db.scalar(select(IngestUserAccess).where(func.lower(IngestUserAccess.email) == norm))
    if not row or not row.active:
        raise HTTPException(status_code=404, detail="Acesso não encontrado.")
    row.active = False
    row.updated_at = datetime.now(timezone.utc)
    record_audit(db, action="ingest.access.revoked", user=user, entity_type="user_access",
                 entity_id=norm, detail={"email": norm})
    db.commit()
