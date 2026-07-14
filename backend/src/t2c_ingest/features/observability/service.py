"""Observabilidade operacional (ponto 14).

Painel do dia baseado NAS TABELAS já registradas (executions, controle, dq_results) — nunca em
leitura pesada do S3 em tempo real. Responde: o que roda agora, o que falhou, o que está atrasado,
fora do SLA, zero registros, watermark parado, origem/destino falhando, duração anômala.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from t2c_ingest.core.config import settings
from t2c_ingest.features.ingestion_control.models import IngestionControl
from t2c_ingest.models.connection import Connection
from t2c_ingest.models.execution import Execution

FREQUENCY_MINUTES = {
    "15min": 15, "30min": 30, "hourly": 60, "2_hours": 120,
    "daily": 1440, "weekly": 10080, "monthly": 43200, "manual": None,
}


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.scheduler_timezone)
    except Exception:  # noqa: BLE001
        return ZoneInfo("America/Sao_Paulo")


def _today_start_utc() -> datetime:
    """Início do dia no fuso operacional, em UTC (executions são tz-aware)."""
    now_local = datetime.now(_tz())
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local.astimezone(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _freq_minutes(control: IngestionControl) -> int | None:
    if control.expected_frequency_minutes:
        return control.expected_frequency_minutes
    return FREQUENCY_MINUTES.get((control.expected_frequency or "").strip())


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ─────────────────────────────── Overview ───────────────────────────────

def overview(db: Session) -> dict:
    today = _today_start_utc()
    base = select(func.count(Execution.id))

    def c(*where):
        stmt = base
        for w in where:
            stmt = stmt.where(w)
        return db.scalar(stmt) or 0

    running_now = c(Execution.status == "running")
    success_today = c(Execution.status == "success", Execution.started_at >= today)
    failed_today = c(Execution.status.in_(("failed", "timeout")), Execution.started_at >= today)
    queued = c(Execution.status == "queued")
    zero_records = c(
        Execution.status == "success", Execution.started_at >= today,
        (Execution.records_written == 0) | (Execution.records_read == 0),
    )
    late = late_loads(db)
    sla = sla_breaches(db)
    stalled = watermark_stalled(db)
    critical_failures = _critical_failures_count(db, today)

    return {
        "date": _now().astimezone(_tz()).date().isoformat(),
        "summary": {
            "running_now": running_now,
            "success_today": success_today,
            "failed_today": failed_today,
            "late_loads": len(late),
            "sla_breaches": len(sla),
            "zero_record_runs": zero_records,
            "watermark_stalled": len(stalled),
            "critical_failures": critical_failures,
        },
        "status_distribution": {
            "success": success_today,
            "failed": failed_today,
            "running": running_now,
            "queued": queued,
        },
    }


def _critical_failures_count(db: Session, since: datetime) -> int:
    # Falhas de hoje cujo controle vinculado é de criticidade alta/crítica.
    stmt = (
        select(func.count(Execution.id))
        .select_from(Execution)
        .join(IngestionControl, IngestionControl.id == Execution.control_id)
        .where(Execution.status.in_(("failed", "timeout")), Execution.started_at >= since,
               IngestionControl.criticality.in_(("alta", "critica")))
    )
    return db.scalar(stmt) or 0


# ─────────────────────────────── Listas do dia ───────────────────────────────

def _conn_names(db: Session) -> dict[int, tuple[str, str]]:
    return {cid: (name, ctype) for cid, name, ctype in
            db.execute(select(Connection.id, Connection.name, Connection.connection_type)).all()}


def _exec_row(e: Execution, controls: dict, conns: dict) -> dict:
    ctrl = controls.get(e.control_id) if e.control_id else None
    src = conns.get(e.source_connection_id)
    tgt = conns.get(e.target_connection_id)
    delay = None
    return {
        "execution_id": e.id, "job_id": e.job_id, "carga": (ctrl.nome_tabela if ctrl else e.target_name),
        "grupo": ctrl.grupo if ctrl else None, "owner": ctrl.owner_name if ctrl else None,
        "criticidade": ctrl.criticality if ctrl else None,
        "control_id": e.control_id, "status": e.status, "engine": e.engine,
        "source": src[0] if src else None, "target": tgt[0] if tgt else (e.destination_type or None),
        "started_at": e.started_at, "finished_at": e.finished_at, "duration_seconds": e.duration_seconds,
        "records_read": e.records_read, "records_written": e.records_written,
        "watermark_before": e.watermark_before, "watermark_after": e.watermark_after,
        "sla_minutes": ctrl.sla_minutes if ctrl else None, "delay_minutes": delay,
    }


def today(db: Session, *, limit: int = 200) -> list[dict]:
    controls = {c.id: c for c in db.scalars(select(IngestionControl)).all()}
    conns = _conn_names(db)
    rows = db.scalars(
        select(Execution).where(Execution.started_at >= _today_start_utc(),
                                Execution.parent_execution_id.is_(None))
        .order_by(Execution.started_at.desc()).limit(limit)
    ).all()
    return [_exec_row(e, controls, conns) for e in rows]


def running(db: Session) -> list[dict]:
    controls = {c.id: c for c in db.scalars(select(IngestionControl)).all()}
    conns = _conn_names(db)
    rows = db.scalars(select(Execution).where(Execution.status == "running").order_by(Execution.started_at.desc()).limit(200)).all()
    return [_exec_row(e, controls, conns) for e in rows]


def failures(db: Session) -> list[dict]:
    controls = {c.id: c for c in db.scalars(select(IngestionControl)).all()}
    conns = _conn_names(db)
    rows = db.scalars(
        select(Execution).where(Execution.status.in_(("failed", "timeout")),
                                Execution.started_at >= _today_start_utc())
        .order_by(Execution.started_at.desc()).limit(200)
    ).all()
    out = []
    for e in rows:
        d = _exec_row(e, controls, conns)
        d["error"] = (e.final_message or "")[:300]
        out.append(d)
    return out


# ─────────────────────────────── Cargas atrasadas ───────────────────────────────

def late_loads(db: Session) -> list[dict]:
    now = _now()
    out = []
    controls = db.scalars(select(IngestionControl).where(IngestionControl.ativo.is_(True))).all()
    for c in controls:
        minutes = _freq_minutes(c)
        last = _as_utc(c.ultima_execucao)
        if not minutes or last is None:
            continue
        deadline = last + timedelta(minutes=minutes)
        if now > deadline:
            atraso = int((now - deadline).total_seconds() // 60)
            out.append({
                "control_id": c.id, "carga": c.nome_tabela, "grupo": c.grupo, "owner": c.owner_name,
                "expected_frequency": c.expected_frequency, "frequency_minutes": minutes,
                "last_execution_at": c.ultima_execucao, "delay_minutes": atraso,
                "criticidade": c.criticality, "status": c.status,
            })
    out.sort(key=lambda x: x["delay_minutes"], reverse=True)
    return out


# ─────────────────────────────── Fora do SLA ───────────────────────────────

def _last_exec_by_control(db: Session) -> dict[int, Execution]:
    """Última execução (por started_at) de cada control_id."""
    sub = (
        select(Execution.control_id, func.max(Execution.id).label("mid"))
        .where(Execution.control_id.is_not(None))
        .group_by(Execution.control_id).subquery()
    )
    rows = db.scalars(select(Execution).join(sub, Execution.id == sub.c.mid)).all()
    return {e.control_id: e for e in rows}


def sla_breaches(db: Session) -> list[dict]:
    out = []
    controls = {c.id: c for c in db.scalars(select(IngestionControl).where(IngestionControl.sla_minutes.is_not(None))).all()}
    last_by_ctrl = _last_exec_by_control(db)
    for cid, c in controls.items():
        e = last_by_ctrl.get(cid)
        if not e or not e.duration_seconds or not c.sla_minutes:
            continue
        sla_s = c.sla_minutes * 60
        if e.duration_seconds > sla_s:
            out.append({
                "control_id": cid, "carga": c.nome_tabela, "owner": c.owner_name,
                "sla_minutes": c.sla_minutes, "duration_seconds": e.duration_seconds,
                "exceeded_seconds": e.duration_seconds - sla_s, "last_status": e.status,
                "criticidade": c.criticality, "execution_id": e.id,
            })
    out.sort(key=lambda x: x["exceeded_seconds"], reverse=True)
    return out


# ─────────────────────────────── Zero registros ───────────────────────────────

def zero_records(db: Session) -> list[dict]:
    controls = {c.id: c for c in db.scalars(select(IngestionControl)).all()}
    conns = _conn_names(db)
    rows = db.scalars(
        select(Execution).where(
            Execution.status == "success", Execution.started_at >= _today_start_utc(),
            (Execution.records_written == 0) | (Execution.records_read == 0),
        ).order_by(Execution.started_at.desc()).limit(200)
    ).all()
    out = []
    for e in rows:
        ctrl = controls.get(e.control_id) if e.control_id else None
        tipo = (ctrl.tipo_ingestao if ctrl else None) or ""
        crit = (ctrl.criticality if ctrl else None) or ""
        # Classificação: incremental sem dados = informativo; full = atenção; crítica = crítico.
        if crit in ("alta", "critica"):
            classe = "critico"
        elif tipo.upper() == "FULL":
            classe = "atencao"
        else:
            classe = "informativo"
        d = _exec_row(e, controls, conns)
        d.update({"tipo_ingestao": tipo or None, "classificacao": classe})
        out.append(d)
    return out


# ─────────────────────────────── Watermark parado ───────────────────────────────

def watermark_stalled(db: Session) -> list[dict]:
    """Cargas incrementais cuja última execução não avançou o watermark."""
    controls = {c.id: c for c in db.scalars(
        select(IngestionControl).where(IngestionControl.tipo_ingestao == "INCREMENTAL", IngestionControl.ativo.is_(True))
    ).all()}
    if not controls:
        return []
    last_by_ctrl = _last_exec_by_control(db)
    out = []
    for cid, c in controls.items():
        e = last_by_ctrl.get(cid)
        if not e:
            continue
        wb, wa = _as_utc(e.watermark_before), _as_utc(e.watermark_after)
        stalled = (wa is None) or (wb is not None and wa is not None and wa <= wb)
        if stalled:
            out.append({
                "control_id": cid, "carga": c.nome_tabela, "owner": c.owner_name,
                "criticidade": c.criticality, "watermark_atual": c.watermark_atual,
                "watermark_before": e.watermark_before, "watermark_after": e.watermark_after,
                "last_execution_at": e.started_at, "execution_id": e.id,
            })
    return out


# ─────────────────────────────── Falhas por origem/destino ───────────────────────────────

def source_target_failures(db: Session) -> dict:
    conns = _conn_names(db)
    since = _today_start_utc()
    fails = db.scalars(
        select(Execution).where(Execution.status.in_(("failed", "timeout")), Execution.started_at >= since)
    ).all()
    agg: dict[tuple, dict] = {}
    for e in fails:
        for role, cid in (("source", e.source_connection_id), ("target", e.target_connection_id)):
            key = (role, cid, e.destination_type)
            if cid is None and role == "source":
                continue
            name = conns.get(cid, (None, None))[0] if cid else (e.destination_type or "—")
            ctype = conns.get(cid, (None, None))[1] if cid else (e.destination_type or None)
            a = agg.setdefault(key, {"role": role, "connection": name, "type": ctype,
                                     "failures_today": 0, "last_failure_at": None, "last_message": None})
            a["failures_today"] += 1
            st = _as_utc(e.started_at)
            if st and (a["last_failure_at"] is None or st > _as_utc(a["last_failure_at"])):
                a["last_failure_at"] = e.started_at
                a["last_message"] = (e.final_message or "")[:200]
    items = [v for v in agg.values() if v["connection"]]
    items.sort(key=lambda x: x["failures_today"], reverse=True)
    return {"items": items}


# ─────────────────────────────── Duração anômala ───────────────────────────────

def duration_anomalies(db: Session) -> list[dict]:
    """Execuções recentes cuja duração > 1.5× a média de sucesso do mesmo job."""
    since = _today_start_utc()
    recent = db.scalars(
        select(Execution).where(Execution.started_at >= since, Execution.duration_seconds.is_not(None),
                                Execution.job_id.is_not(None))
        .order_by(Execution.started_at.desc()).limit(500)
    ).all()
    if not recent:
        return []
    job_ids = {e.job_id for e in recent}
    avg_rows = db.execute(
        select(Execution.job_id, func.avg(Execution.duration_seconds), func.count(Execution.id))
        .where(Execution.job_id.in_(job_ids), Execution.status == "success",
               Execution.duration_seconds.is_not(None))
        .group_by(Execution.job_id)
    ).all()
    avgs = {jid: (float(avg), n) for jid, avg, n in avg_rows}
    controls = {c.id: c for c in db.scalars(select(IngestionControl)).all()}
    out = []
    for e in recent:
        avg_n = avgs.get(e.job_id)
        if not avg_n:
            continue
        avg, n = avg_n
        if n < 3 or avg <= 0:  # histórico insuficiente
            continue
        if e.duration_seconds > avg * 1.5:
            ctrl = controls.get(e.control_id) if e.control_id else None
            out.append({
                "execution_id": e.id, "job_id": e.job_id,
                "carga": (ctrl.nome_tabela if ctrl else e.target_name),
                "duration_seconds": e.duration_seconds, "avg_seconds": round(avg, 1),
                "ratio": round(e.duration_seconds / avg, 2), "status": e.status,
            })
    out.sort(key=lambda x: x["ratio"], reverse=True)
    return out


# ─────────────────────────────── Health / SLA por carga ───────────────────────────────

def control_health(db: Session) -> list[dict]:
    now = _now()
    controls = db.scalars(select(IngestionControl).order_by(IngestionControl.nome_tabela)).all()
    last_by_ctrl = _last_exec_by_control(db)
    out = []
    for c in controls:
        e = last_by_ctrl.get(c.id)
        minutes = _freq_minutes(c)
        last = _as_utc(c.ultima_execucao) or (_as_utc(e.started_at) if e else None)
        is_late = bool(minutes and last and now > last + timedelta(minutes=minutes))
        dur = e.duration_seconds if e else None
        sla_breached = bool(c.sla_minutes and dur and dur > c.sla_minutes * 60)
        rr = e.records_read if e else None
        rw = e.records_written if e else None
        zero = bool(e and e.status == "success" and ((rw == 0) or (rr == 0)))
        wb, wa = (_as_utc(e.watermark_before), _as_utc(e.watermark_after)) if e else (None, None)
        wm_stalled = bool((c.tipo_ingestao or "").upper() == "INCREMENTAL" and e and
                          ((wa is None) or (wb is not None and wa is not None and wa <= wb)))
        q = (e.quality_summary or {}) if e else {}
        out.append({
            "control_id": c.id, "name": c.nome_tabela, "group": c.grupo, "owner": c.owner_name,
            "criticality": c.criticality, "status": (e.status if e else c.status),
            "last_execution_at": (e.started_at if e else c.ultima_execucao),
            "expected_frequency": c.expected_frequency, "is_late": is_late,
            "sla_minutes": c.sla_minutes, "last_duration_seconds": dur, "sla_breached": sla_breached,
            "records_read": rr, "records_written": rw, "zero_records": zero,
            "watermark_stalled": wm_stalled, "last_quality_status": q.get("overall"),
        })
    return out


def sla_report(db: Session) -> dict:
    health = control_health(db)
    late = [h for h in health if h["is_late"]]
    breaches = [h for h in health if h["sla_breached"]]
    critical_late = [h for h in late if (h["criticality"] in ("alta", "critica"))]
    return {
        "summary": {
            "total_controls": len(health),
            "late_loads": len(late),
            "sla_breaches": len(breaches),
            "critical_late": len(critical_late),
        },
        "items": [h for h in health if h["is_late"] or h["sla_breached"]],
    }
