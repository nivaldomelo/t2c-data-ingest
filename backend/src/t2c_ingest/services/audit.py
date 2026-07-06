from __future__ import annotations

from sqlalchemy.orm import Session

from t2c_ingest.features.auth_bridge.deps import CurrentUser
from t2c_ingest.models.audit import AuditEvent


def record_audit(
    db: Session,
    *,
    action: str,
    user: CurrentUser | None = None,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    detail: dict | None = None,
) -> None:
    """Best-effort audit write. Never raises: auditing must not break the request path."""
    try:
        event = AuditEvent(
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            user_email=user.email if user else None,
            user_id=user.id if user else None,
            detail=detail,
        )
        db.add(event)
        db.flush()
    except Exception:  # noqa: BLE001
        db.rollback()
