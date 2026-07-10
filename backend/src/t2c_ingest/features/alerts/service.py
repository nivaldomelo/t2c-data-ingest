"""Alerts: match events to channels, record notifications and deliver to Teams/Slack/webhook.

emit() creates one pending notification per matching channel; dispatch_pending() (called by the
worker) POSTs them and records the result. Delivery is best-effort and never breaks the caller.
"""
from __future__ import annotations

import json
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

from sqlalchemy import or_, select
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


def _send_email(target: str, notif: AlertNotification) -> None:
    """Send an email notification via SMTP. Raises on failure (caught by send_one)."""
    if not settings.smtp_host:
        raise RuntimeError("SMTP não configurado (defina SMTP_HOST).")
    recipients = [r.strip() for r in target.replace(";", ",").split(",") if r.strip()]
    if not recipients:
        raise RuntimeError("Canal de e-mail sem destinatário.")
    link = _link(notif)
    body = f"{notif.title}\n\n{notif.message or ''}\n\nEvento: {notif.event_type} · Severidade: {notif.severity.upper()}"
    if link:
        body += f"\n\n{link}"
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"[T2C Data Ingest · {notif.severity.upper()}] {notif.title}"
    msg["From"] = settings.smtp_from or settings.smtp_user or "t2c-data-ingest@localhost"
    msg["To"] = ", ".join(recipients)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.sendmail(msg["From"], recipients, msg.as_string())


def send_one(db: Session, notif: AlertNotification, channel: AlertChannel) -> None:
    """Deliver a single notification to its channel and record the outcome."""
    notif.attempts += 1
    try:
        target = decrypt_secret(channel.target_url_encrypted)
        if channel.channel_type == "email":
            _send_email(target, notif)
            notif.http_status = None
            notif.status = "sent"
            notif.error = None
        else:
            payload = json.dumps(build_payload(channel.channel_type, notif)).encode()
            # SSRF-safe POST: validates + PINS the connection to a public IP (no DNS-rebinding).
            code = safe_post(
                target, payload, {"Content-Type": "application/json"}, timeout=10,
                allow_internal=settings.alerts_allow_internal_targets,
            )
            notif.http_status = code
            notif.status = "sent" if 200 <= code < 300 else "failed"
            notif.error = None if notif.status == "sent" else f"HTTP {code}"
    except Exception as exc:  # noqa: BLE001
        notif.status = "failed"
        notif.error = str(exc)[:500]
    # After exhausting retries, mark 'dead' so it stops being retried and is visible.
    if notif.status == "failed" and notif.attempts >= settings.alert_max_attempts:
        notif.status = "dead"
    notif.sent_at = _now()


def _retry_due(notif: AlertNotification, now: datetime) -> bool:
    """A failed notification is due for retry after an exponential backoff since last attempt."""
    if notif.status != "failed" or notif.attempts >= settings.alert_max_attempts:
        return False
    if not notif.sent_at:
        return True
    backoff = settings.alert_retry_base_seconds * (2 ** max(0, notif.attempts - 1))
    return notif.sent_at + timedelta(seconds=min(backoff, 3600)) <= now


def dispatch_pending(db: Session, limit: int = 20) -> int:
    """Send pending notifications and retry due failed ones (exponential backoff). Returns count."""
    now = _now()
    candidates = db.scalars(
        select(AlertNotification)
        .where(or_(AlertNotification.status == "pending", AlertNotification.status == "failed"))
        .order_by(AlertNotification.id)
        .limit(limit * 3)
    ).all()
    to_send = [n for n in candidates if n.status == "pending" or _retry_due(n, now)][:limit]
    if not to_send:
        return 0
    channels = {c.id: c for c in db.scalars(select(AlertChannel)).all()}
    for notif in to_send:
        ch = channels.get(notif.channel_id)
        if not ch:
            notif.status = "dead"
            notif.error = "Canal removido."
            continue
        send_one(db, notif, ch)
    db.commit()
    return len(to_send)
