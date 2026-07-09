"""Alerts: match events to channels, record notifications and deliver to Teams/Slack/webhook.

emit() creates one pending notification per matching channel; dispatch_pending() (called by the
worker) POSTs them and records the result. Delivery is best-effort and never breaks the caller.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from t2c_ingest.core.config import settings
from t2c_ingest.core.crypto import decrypt_secret
from t2c_ingest.core.ssrf import safe_post
from t2c_ingest.models.alert import AlertChannel, AlertNotification, SEVERITY_RANK

FRONTEND_BASE = "http://localhost:3001"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def emit(db: Session, *, event_type: str, severity: str, title: str, message: str | None = None,
         job_id: int | None = None, pipeline_id: int | None = None, execution_id: int | None = None) -> int:
    """Create pending notifications for every active channel subscribed to this event/severity.

    Best-effort: never raises. Returns the number of notifications queued.
    """
    try:
        channels = db.scalars(select(AlertChannel).where(AlertChannel.active.is_(True))).all()
        queued = 0
        for ch in channels:
            events = ch.events or []
            if events and event_type not in events:
                continue
            if SEVERITY_RANK.get(severity, 1) < SEVERITY_RANK.get(ch.min_severity, 1):
                continue
            db.add(AlertNotification(
                channel_id=ch.id, event_type=event_type, severity=severity, title=title, message=message,
                job_id=job_id, pipeline_id=pipeline_id, execution_id=execution_id, status="pending",
            ))
            queued += 1
        if queued:
            db.flush()
        return queued
    except Exception:  # noqa: BLE001
        db.rollback()
        return 0


def _link(notif: AlertNotification) -> str | None:
    if notif.execution_id:
        return f"{FRONTEND_BASE}/executions/{notif.execution_id}"
    if notif.pipeline_id:
        return f"{FRONTEND_BASE}/pipelines/{notif.pipeline_id}"
    if notif.job_id:
        return f"{FRONTEND_BASE}/jobs/{notif.job_id}"
    return None


_COLOR = {"info": "2563EB", "warning": "F59E0B", "critical": "DC2626"}


def build_payload(channel_type: str, notif: AlertNotification) -> dict:
    """Render the channel-specific JSON body for a notification."""
    link = _link(notif)
    text = notif.message or notif.title
    if channel_type == "teams":
        card: dict = {
            "@type": "MessageCard", "@context": "http://schema.org/extensions",
            "themeColor": _COLOR.get(notif.severity, "F59E0B"),
            "summary": notif.title,
            "sections": [{
                "activityTitle": f"T2C Data Ingest · {notif.title}",
                "activitySubtitle": f"{notif.event_type} · {notif.severity.upper()}",
                "text": text,
            }],
        }
        if link:
            card["potentialAction"] = [{"@type": "OpenUri", "name": "Abrir no T2C Data Ingest",
                                        "targets": [{"os": "default", "uri": link}]}]
        return card
    if channel_type == "slack":
        body = f"*{notif.title}*\n{text}"
        if link:
            body += f"\n<{link}|Abrir no T2C Data Ingest>"
        return {"text": body}
    # generic webhook
    return {
        "title": notif.title, "message": text, "event": notif.event_type, "severity": notif.severity,
        "job_id": notif.job_id, "pipeline_id": notif.pipeline_id, "execution_id": notif.execution_id,
        "link": link, "product": "t2c-data-ingest",
    }


def send_one(db: Session, notif: AlertNotification, channel: AlertChannel) -> None:
    """POST a single notification to its channel and record the outcome."""
    notif.attempts += 1
    try:
        url = decrypt_secret(channel.target_url_encrypted)
        payload = json.dumps(build_payload(channel.channel_type, notif)).encode()
        # SSRF-safe POST: validates + PINS the connection to a public IP (no DNS-rebinding),
        # does not follow redirects.
        code = safe_post(
            url, payload, {"Content-Type": "application/json"}, timeout=10,
            allow_internal=settings.alerts_allow_internal_targets,
        )
        notif.http_status = code
        notif.status = "sent" if 200 <= code < 300 else "failed"
        notif.error = None if notif.status == "sent" else f"HTTP {code}"
    except Exception as exc:  # noqa: BLE001
        notif.status = "failed"
        notif.error = str(exc)[:500]
    notif.sent_at = _now()


def dispatch_pending(db: Session, limit: int = 20) -> int:
    """Send queued notifications (called each worker tick). Returns how many were processed."""
    pending = db.scalars(
        select(AlertNotification).where(AlertNotification.status == "pending").order_by(AlertNotification.id).limit(limit)
    ).all()
    if not pending:
        return 0
    channels = {c.id: c for c in db.scalars(select(AlertChannel)).all()}
    for notif in pending:
        ch = channels.get(notif.channel_id)
        if not ch:
            notif.status = "failed"
            notif.error = "Canal removido."
            continue
        send_one(db, notif, ch)
    db.commit()
    return len(pending)
