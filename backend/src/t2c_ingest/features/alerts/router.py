from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from t2c_ingest.core.config import settings
from t2c_ingest.core.crypto import encrypt_secret
from t2c_ingest.core.db import get_db
from t2c_ingest.core.ssrf import assert_public_http_url
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.alerts import service
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.models.alert import AlertChannel, AlertNotification, CHANNEL_TYPES, SEVERITIES
from t2c_ingest.schemas.alert import (
    ChannelCreate,
    ChannelOut,
    ChannelUpdate,
    NotificationOut,
    TestChannelResult,
)
from t2c_ingest.services.audit import record_audit

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _mask(url: str) -> str:
    try:
        p = urlparse(url)
        host = p.hostname or ""
        return f"{p.scheme}://{host}/…" if host else "configurado"
    except Exception:  # noqa: BLE001
        return "configurado"


def _channel_out(ch: AlertChannel) -> ChannelOut:
    from t2c_ingest.core.crypto import decrypt_secret
    out = ChannelOut.model_validate(ch)
    try:
        out.target_masked = _mask(decrypt_secret(ch.target_url_encrypted))
    except Exception:  # noqa: BLE001
        out.target_masked = "configurado"
    return out


def _validate(channel_type: str | None, severity: str | None) -> None:
    if channel_type is not None and channel_type not in CHANNEL_TYPES:
        raise HTTPException(422, f"Tipo de canal inválido. Use: {', '.join(CHANNEL_TYPES)}.")
    if severity is not None and severity not in SEVERITIES:
        raise HTTPException(422, f"Severidade inválida. Use: {', '.join(SEVERITIES)}.")


def _validate_url(url: str) -> None:
    """SSRF guard on the webhook URL (rejects internal/metadata targets)."""
    try:
        assert_public_http_url(url or "", allow_internal=settings.alerts_allow_internal_targets)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


# ── channels ──
@router.get("/channels", response_model=list[ChannelOut])
def list_channels(db: Session = Depends(get_db), _: CurrentUser = Depends(require_permission(perms.INGEST_ALERTS_READ))) -> list[ChannelOut]:
    rows = db.scalars(select(AlertChannel).order_by(AlertChannel.name)).all()
    return [_channel_out(c) for c in rows]


@router.post("/channels", response_model=ChannelOut, status_code=status.HTTP_201_CREATED)
def create_channel(payload: ChannelCreate, db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission(perms.INGEST_ALERTS_MANAGE))) -> ChannelOut:
    _validate(payload.channel_type, payload.min_severity)
    _validate_url(payload.target_url)
    ch = AlertChannel(
        name=payload.name.strip(), channel_type=payload.channel_type,
        target_url_encrypted=encrypt_secret(payload.target_url.strip()),
        active=payload.active, events=payload.events or None, min_severity=payload.min_severity,
        created_by=user.email,
    )
    db.add(ch)
    db.flush()
    record_audit(db, action="ALERT_CHANNEL_CREATED", user=user, entity_type="alert_channel", entity_id=ch.id,
                 detail={"name": ch.name, "type": ch.channel_type})
    db.commit()
    db.refresh(ch)
    return _channel_out(ch)


@router.patch("/channels/{channel_id}", response_model=ChannelOut)
def update_channel(channel_id: int, payload: ChannelUpdate, db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission(perms.INGEST_ALERTS_MANAGE))) -> ChannelOut:
    ch = db.get(AlertChannel, channel_id)
    if not ch:
        raise HTTPException(404, "Canal não encontrado")
    _validate(payload.channel_type, payload.min_severity)
    data = payload.model_dump(exclude_unset=True)
    if "target_url" in data and data["target_url"]:
        _validate_url(data["target_url"])
        ch.target_url_encrypted = encrypt_secret(data.pop("target_url").strip())
    else:
        data.pop("target_url", None)
    if "events" in data:
        ch.events = data.pop("events") or None
    for k, v in data.items():
        setattr(ch, k, v)
    record_audit(db, action="ALERT_CHANNEL_UPDATED", user=user, entity_type="alert_channel", entity_id=ch.id)
    db.commit()
    db.refresh(ch)
    return _channel_out(ch)


@router.delete("/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(channel_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission(perms.INGEST_ALERTS_MANAGE))) -> None:
    ch = db.get(AlertChannel, channel_id)
    if not ch:
        raise HTTPException(404, "Canal não encontrado")
    db.delete(ch)
    record_audit(db, action="ALERT_CHANNEL_DELETED", user=user, entity_type="alert_channel", entity_id=channel_id)
    db.commit()


@router.post("/channels/{channel_id}/test", response_model=TestChannelResult)
def test_channel(channel_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission(perms.INGEST_ALERTS_MANAGE))) -> TestChannelResult:
    ch = db.get(AlertChannel, channel_id)
    if not ch:
        raise HTTPException(404, "Canal não encontrado")
    notif = AlertNotification(
        channel_id=ch.id, event_type="TEST", severity="info",
        title="Teste de alerta — T2C Data Ingest",
        message=f"Notificação de teste enviada por {user.email}.", status="pending",
    )
    db.add(notif)
    db.flush()
    service.send_one(db, notif, ch)
    db.commit()
    return TestChannelResult(status=notif.status, http_status=notif.http_status, error=notif.error)


# ── notifications history ──
@router.get("/notifications", response_model=PageOut[NotificationOut])
def list_notifications(
    params: PageParams = Depends(),
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_ALERTS_READ)),
) -> PageOut[NotificationOut]:
    stmt = select(AlertNotification)
    count_stmt = select(func.count(AlertNotification.id))
    if status_filter:
        stmt = stmt.where(AlertNotification.status == status_filter)
        count_stmt = count_stmt.where(AlertNotification.status == status_filter)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(AlertNotification.id.desc()).offset(params.offset).limit(params.limit)).all()
    names = {c.id: c.name for c in db.scalars(select(AlertChannel)).all()}
    items = []
    for n in rows:
        o = NotificationOut.model_validate(n)
        o.channel_name = names.get(n.channel_id)
        items.append(o)
    return PageOut.build(items, total, params)


@router.post("/notifications/{notification_id}/resend", response_model=NotificationOut)
def resend(notification_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission(perms.INGEST_ALERTS_MANAGE))) -> NotificationOut:
    n = db.get(AlertNotification, notification_id)
    if not n:
        raise HTTPException(404, "Notificação não encontrada")
    ch = db.get(AlertChannel, n.channel_id) if n.channel_id else None
    if not ch:
        raise HTTPException(409, "Canal da notificação não existe mais.")
    service.send_one(db, n, ch)
    record_audit(db, action="ALERT_RESENT", user=user, entity_type="alert_notification", entity_id=n.id)
    db.commit()
    db.refresh(n)
    out = NotificationOut.model_validate(n)
    out.channel_name = ch.name
    return out
