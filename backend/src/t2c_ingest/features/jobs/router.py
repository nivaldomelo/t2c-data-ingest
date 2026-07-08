from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.connections.repository import get_connection_by_ref
from t2c_ingest.features.jobs.archive_service import ArchiveError, archive_job_code
from t2c_ingest.features.jobs.code_service import (
    CodeError,
    assert_within_allowed,
    detect_language,
    file_metadata,
    is_editable_extension,
    provision_job_script,
    read_job_code,
    write_job_code,
)
from t2c_ingest.models.pipeline import PipelineDefinition, PipelineStep
from t2c_ingest.features.tags.service import job_ids_with_tags, sync_job_tags, tags_for_jobs
from t2c_ingest.models.connection import Connection
from t2c_ingest.models.execution import Execution
from t2c_ingest.models.job import JobDefinition
from t2c_ingest.models.tag import JobTag, Tag
from t2c_ingest.schemas.execution import ExecutionOut
from t2c_ingest.schemas.tag import JobTagsUpdate, TagLite
from t2c_ingest.features.schedules.manager import create_schedule, schedule_out
from t2c_ingest.models.job_code_version import JobCodeVersion
from t2c_ingest.models.schedule import JobSchedule
from t2c_ingest.schemas.schedule import ScheduleCreate, ScheduleOut
from t2c_ingest.schemas.job import (
    JobCodeOut,
    JobCodeSaveRequest,
    JobCreate,
    JobDeleteRequest,
    JobDeleteResult,
    JobDetailOut,
    JobOut,
    JobRunRequest,
    JobSearchOut,
    JobUpdate,
)
from t2c_ingest.services.audit import record_audit
from t2c_ingest.services.execution_service import enqueue_job_execution

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_out_with_tags(db: Session, jobs: list[JobDefinition]) -> list[JobOut]:
    tags_map = tags_for_jobs(db, [j.id for j in jobs])
    outs = []
    for j in jobs:
        o = JobOut.model_validate(j)
        o.tags = [TagLite.model_validate(t) for t in tags_map.get(j.id, [])]
        outs.append(o)
    return outs


@router.get("", response_model=PageOut[JobOut])
def list_jobs(
    params: PageParams = Depends(),
    type: str | None = None,
    is_active: bool | None = None,
    tags: str | None = Query(None, description="Slugs/nomes separados por vírgula"),
    include_deleted: bool = Query(False, description="Inclui jobs excluídos (arquivados)"),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_READ)),
) -> PageOut[JobOut]:
    stmt = select(JobDefinition)
    count_stmt = select(func.count(JobDefinition.id))
    if not include_deleted:
        stmt = stmt.where(JobDefinition.deleted_at.is_(None))
        count_stmt = count_stmt.where(JobDefinition.deleted_at.is_(None))
    if type:
        stmt = stmt.where(JobDefinition.type == type)
        count_stmt = count_stmt.where(JobDefinition.type == type)
    if is_active is not None:
        stmt = stmt.where(JobDefinition.is_active == is_active)
        count_stmt = count_stmt.where(JobDefinition.is_active == is_active)
    if tags:
        ids = job_ids_with_tags(db, tags.split(",")) or {-1}
        stmt = stmt.where(JobDefinition.id.in_(ids))
        count_stmt = count_stmt.where(JobDefinition.id.in_(ids))
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(JobDefinition.name).offset(params.offset).limit(params.limit)
    ).all()
    return PageOut.build(_job_out_with_tags(db, rows), total, params)


@router.get("/search", response_model=list[JobSearchOut])
def search_jobs(
    search: str | None = None,
    tags: str | None = Query(None, description="Slugs/nomes separados por vírgula"),
    job_type: str | None = None,
    engine: str | None = None,
    active: bool | None = None,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_READ)),
) -> list[JobSearchOut]:
    """Autocomplete for the pipeline builder command palette (matches name/description/tags)."""
    stmt = select(JobDefinition).where(JobDefinition.deleted_at.is_(None))
    if search:
        like = f"%{search.strip()}%"
        # Jobs whose name/description match, OR that carry a tag matching the term.
        tag_job_ids = {
            r[0]
            for r in db.execute(
                select(JobTag.job_id).join(Tag, Tag.id == JobTag.tag_id).where(or_(Tag.name.ilike(like), Tag.slug.ilike(like)))
            ).all()
        }
        conds = [JobDefinition.name.ilike(like), JobDefinition.description.ilike(like)]
        if tag_job_ids:
            conds.append(JobDefinition.id.in_(tag_job_ids))
        stmt = stmt.where(or_(*conds))
    if tags:
        ids = job_ids_with_tags(db, tags.split(",")) or {-1}
        stmt = stmt.where(JobDefinition.id.in_(ids))
    if job_type:
        stmt = stmt.where(JobDefinition.type == job_type)
    if engine:
        stmt = stmt.where(JobDefinition.engine == engine)
    if active is not None:
        stmt = stmt.where(JobDefinition.is_active == active)
    rows = db.scalars(stmt.order_by(JobDefinition.name).limit(limit)).all()
    tags_map = tags_for_jobs(db, [j.id for j in rows])
    return [
        JobSearchOut(id=j.id, name=j.name, description=j.description, job_type=j.type, engine=j.engine, active=j.is_active,
                     tags=[TagLite.model_validate(t) for t in tags_map.get(j.id, [])])
        for j in rows
    ]


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_WRITE)),
) -> JobOut:
    if db.scalar(select(JobDefinition).where(JobDefinition.name == payload.name)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job name already exists")
    job = JobDefinition(**payload.model_dump(), created_by=user.email, updated_by=user.email)
    db.add(job)
    db.flush()
    # Every job is born versioned: an explicit script_path must live inside an allowed
    # (git-tracked) dir; otherwise we provision one under spark/jobs or python_jobs.
    try:
        if job.script_path and job.script_path.strip():
            assert_within_allowed(job.script_path)
        else:
            job.script_path = provision_job_script(job.type, job.name, job.id)
    except CodeError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    record_audit(db, action="ingest.job.created", user=user, entity_type="job", entity_id=job.id)
    db.commit()
    db.refresh(job)
    return JobOut.model_validate(job)


def _connection_name(db: Session, connection_id: int | None) -> str | None:
    if not connection_id:
        return None
    conn = db.get(Connection, connection_id)
    return conn.name if conn else None


def _arg_connection_name(job: JobDefinition, flag: str) -> str | None:
    """Fallback: read a connection name from the job arguments (--source-connection etc.)."""
    args = [str(a) for a in (job.arguments or [])]
    for i, a in enumerate(args):
        if a == flag and i + 1 < len(args):
            return args[i + 1]
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return None


def _jsonable(d: dict) -> dict:
    """Coerce a dict of model values to JSON-safe primitives for the audit trail."""
    out: dict = {}
    for k, v in d.items():
        out[k] = v if (v is None or isinstance(v, (str, int, float, bool, list, dict))) else str(v)
    return out


# Execution statuses that mean the job is still active (cannot be deleted).
_RUNNING_STATES = ("queued", "running")


def _delete_blockers(db: Session, job_id: int) -> str | None:
    """Return a human message if the job has an active dependency blocking deletion, else None."""
    running = db.scalar(
        select(func.count(Execution.id)).where(
            Execution.job_id == job_id, Execution.status.in_(_RUNNING_STATES)
        )
    )
    if running:
        return "Não é possível excluir um job em execução."
    active_pipelines = db.scalar(
        select(func.count(PipelineStep.id))
        .join(PipelineDefinition, PipelineDefinition.id == PipelineStep.pipeline_id)
        .where(
            PipelineStep.job_id == job_id,
            PipelineStep.active.is_(True),
            PipelineDefinition.is_active.is_(True),
        )
    )
    if active_pipelines:
        return ("Este job está vinculado a pipelines ativos. Remova o job dos pipelines ou "
                "inative os pipelines antes de excluir.")
    active_schedules = db.scalar(
        select(func.count(JobSchedule.id)).where(
            JobSchedule.job_id == job_id, JobSchedule.active.is_(True)
        )
    )
    if active_schedules:
        return "Este job possui schedules ativos. Desative os schedules antes de excluir."
    return None


@router.get("/{job_id}", response_model=JobDetailOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_READ)),
) -> JobDetailOut:
    job = db.get(JobDefinition, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    detail = JobDetailOut.model_validate(job)
    detail.source_connection_name = _connection_name(db, job.source_connection_id) or _arg_connection_name(
        job, "--source-connection"
    )
    detail.target_connection_name = _connection_name(db, job.target_connection_id) or _arg_connection_name(
        job, "--target-connection"
    )

    detail.executions_total = (
        db.scalar(select(func.count(Execution.id)).where(Execution.job_id == job_id)) or 0
    )
    last = db.scalar(
        select(Execution).where(Execution.job_id == job_id).order_by(Execution.id.desc()).limit(1)
    )
    if last:
        detail.last_execution_id = last.id
        detail.last_status = last.status
        detail.last_finished_at = last.finished_at
    avg = db.scalar(
        select(func.avg(Execution.duration_seconds)).where(
            Execution.job_id == job_id, Execution.status == "success"
        )
    )
    detail.avg_duration_seconds = float(avg) if avg is not None else None
    detail.tags = [TagLite.model_validate(t) for t in tags_for_jobs(db, [job.id]).get(job.id, [])]
    return detail


@router.get("/{job_id}/tags", response_model=list[TagLite])
def get_job_tags(
    job_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_READ)),
) -> list[TagLite]:
    if not db.get(JobDefinition, job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return [TagLite.model_validate(t) for t in tags_for_jobs(db, [job_id]).get(job_id, [])]


@router.put("/{job_id}/tags", response_model=list[TagLite])
def put_job_tags(
    job_id: int,
    payload: JobTagsUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_JOBS_TAGS_WRITE)),
) -> list[TagLite]:
    if not db.get(JobDefinition, job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    final = sync_job_tags(db, job_id, payload.tags, user_id=user.id)
    record_audit(db, action="JOB_TAGS_UPDATED", user=user, entity_type="job", entity_id=job_id,
                 detail={"tags": [t.slug for t in final]})
    db.commit()
    return [TagLite.model_validate(t) for t in final]


@router.patch("/{job_id}", response_model=JobOut)
@router.put("/{job_id}", response_model=JobOut)
def update_job(
    job_id: int,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_WRITE)),
) -> JobOut:
    job = db.get(JobDefinition, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este job foi excluído e não pode ser editado.")
    changes = payload.model_dump(exclude_unset=True)
    # A script_path (when provided) must stay inside an allowed (git-tracked) directory.
    new_path = changes.get("script_path")
    if new_path is not None and str(new_path).strip():
        try:
            assert_within_allowed(str(new_path))
        except CodeError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    before = {k: getattr(job, k) for k in changes}
    for key, value in changes.items():
        setattr(job, key, value)
    job.updated_by = user.email
    record_audit(db, action="JOB_UPDATED", user=user, entity_type="job", entity_id=job.id,
                 detail={"before": _jsonable(before), "after": _jsonable(changes)})
    db.commit()
    db.refresh(job)
    return JobOut.model_validate(job)


@router.delete("/{job_id}", response_model=JobDeleteResult)
def delete_job(
    job_id: int,
    payload: JobDeleteRequest | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_JOBS_DELETE)),
) -> JobDeleteResult:
    """Soft-delete a job: archive its code first (never hard-delete), then mark it deleted.

    Blocks if the job is running or still referenced by active pipelines/schedules.
    """
    job = db.get(JobDefinition, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este job já foi excluído.")

    reason = payload.reason if payload else None
    record_audit(db, action="JOB_DELETE_REQUESTED", user=user, entity_type="job", entity_id=job.id,
                 detail={"job_name": job.name, "reason": reason})

    # 1) Dependency checks — block (don't archive) if the job is still active somewhere.
    blocker = _delete_blockers(db, job_id)
    if blocker:
        record_audit(db, action="JOB_DELETE_BLOCKED", user=user, entity_type="job", entity_id=job.id,
                     detail={"job_name": job.name, "reason": blocker})
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=blocker)

    # 2) Archive the code. On failure we abort the delete (nothing is lost).
    now = datetime.now(timezone.utc)
    try:
        archived = archive_job_code(job, deleted_by=user.email, now=now)
    except ArchiveError as exc:
        record_audit(db, action="JOB_DELETE_BLOCKED", user=user, entity_type="job", entity_id=job.id,
                     detail={"job_name": job.name, "reason": f"archive_failed: {exc.message}"})
        db.commit()
        raise HTTPException(status_code=exc.status, detail=f"Falha ao arquivar o código do job: {exc.message}") from exc

    archived_path = archived["archived_code_path"]
    record_audit(db, action="JOB_CODE_ARCHIVED", user=user, entity_type="job", entity_id=job.id,
                 detail={"job_name": job.name, "archived_code_path": archived_path,
                         "file_count": archived.get("file_count"), "original_removed": archived.get("original_removed")})
    db.add(JobCodeVersion(
        job_id=job.id, script_path=job.script_path or "", action="archived_on_job_delete",
        file_path=archived.get("original_workspace_path"), backup_path=archived["archived_workspace_path"],
        changed_by=user.email, size_before_bytes=None,
        change_summary=f"Código arquivado antes da exclusão lógica ({archived.get('file_count')} arquivos).",
    ))

    # 3) Soft delete.
    job.deleted_at = now
    job.deleted_by = user.email
    job.delete_reason = reason
    job.is_active = False
    job.archived_code_path = archived_path
    job.updated_by = user.email
    record_audit(db, action="JOB_DELETED", user=user, entity_type="job", entity_id=job.id,
                 detail={"job_name": job.name, "archived_code_path": archived_path, "reason": reason})
    db.commit()
    return JobDeleteResult(
        success=True,
        message="Job excluído com sucesso. Código arquivado.",
        job_id=job.id,
        archived_code_path=archived_path,
    )


@router.post("/{job_id}/run", response_model=ExecutionOut, status_code=status.HTTP_202_ACCEPTED)
def run_job(
    job_id: int,
    payload: JobRunRequest | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_RUN)),
) -> ExecutionOut:
    job = db.get(JobDefinition, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este job foi excluído e não pode ser executado.")
    execution = enqueue_job_execution(
        db, job=job, user=user, parameters=(payload.parameters if payload else None)
    )
    db.commit()
    db.refresh(execution)
    return ExecutionOut.model_validate(execution)


@router.get("/{job_id}/executions", response_model=PageOut[ExecutionOut])
def job_executions(
    job_id: int,
    params: PageParams = Depends(),
    status_filter: str | None = Query(None, alias="status"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    user_id: str | None = Query(None, description="Filtra por quem disparou (e-mail)"),
    search: str | None = Query(None, description="Busca na mensagem final / alvo"),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_READ)),
) -> PageOut[ExecutionOut]:
    if not db.get(JobDefinition, job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    filters = [Execution.job_id == job_id]
    if status_filter:
        filters.append(Execution.status == status_filter)
    if date_from:
        filters.append(Execution.created_at >= date_from)
    if date_to:
        filters.append(Execution.created_at <= date_to)
    if user_id:
        filters.append(Execution.triggered_by == user_id)
    if search:
        like = f"%{search.strip()}%"
        filters.append(or_(Execution.final_message.ilike(like), Execution.target_name.ilike(like)))

    count_stmt = select(func.count(Execution.id))
    stmt = select(Execution)
    for f in filters:
        count_stmt = count_stmt.where(f)
        stmt = stmt.where(f)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(Execution.id.desc()).offset(params.offset).limit(params.limit)
    ).all()
    return PageOut.build([ExecutionOut.model_validate(r) for r in rows], total, params)


def _code_out(db: Session, job: JobDefinition, user: CurrentUser) -> JobCodeOut:
    import os

    content = read_job_code(job.script_path or "")
    meta = file_metadata(job.script_path or "")
    can_write = user.has(perms.INGEST_JOBS_CODE_WRITE) and is_editable_extension(job.script_path or "")
    return JobCodeOut(
        job_id=job.id,
        job_name=job.name,
        script_path=job.script_path,
        file_name=os.path.basename(job.script_path or "") or None,
        language=detect_language(job.script_path or "", job.type),
        content=content,
        editable=can_write,
        read_only=not can_write,
        last_modified_at=meta["last_modified_at"],
        size_bytes=meta["size_bytes"],
    )


@router.get("/{job_id}/schedules", response_model=PageOut[ScheduleOut])
def job_schedules(
    job_id: int,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_SCHEDULES_READ)),
) -> PageOut[ScheduleOut]:
    if not db.get(JobDefinition, job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    total = db.scalar(select(func.count(JobSchedule.id)).where(JobSchedule.job_id == job_id)) or 0
    rows = db.scalars(
        select(JobSchedule)
        .where(JobSchedule.job_id == job_id)
        .order_by(JobSchedule.name)
        .offset(params.offset)
        .limit(params.limit)
    ).all()
    return PageOut.build([schedule_out(db, r) for r in rows], total, params)


@router.post("/{job_id}/schedules", response_model=ScheduleOut, status_code=status.HTTP_201_CREATED)
def create_job_schedule(
    job_id: int,
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_SCHEDULES_WRITE)),
) -> ScheduleOut:
    if not db.get(JobDefinition, job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    from t2c_ingest.features.schedules.service import is_valid_cron

    if payload.cron_expression and not is_valid_cron(payload.cron_expression):
        raise HTTPException(status_code=422, detail="Expressão cron inválida.")
    sch = create_schedule(db, job_id=job_id, payload=payload, user=user)
    db.commit()
    return schedule_out(db, db.get(JobSchedule, sch.id))


@router.get("/{job_id}/code", response_model=JobCodeOut)
def job_code(
    job_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_JOBS_CODE_READ)),
) -> JobCodeOut:
    job = db.get(JobDefinition, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    try:
        return _code_out(db, job, user)
    except CodeError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc


@router.put("/{job_id}/code", response_model=JobCodeOut)
def save_job_code(
    job_id: int,
    payload: JobCodeSaveRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_JOBS_CODE_WRITE)),
) -> JobCodeOut:
    job = db.get(JobDefinition, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    try:
        result = write_job_code(
            job.script_path or "",
            payload.content,
            payload.expected_last_modified_at,
            job_id=job.id,
        )
    except CodeError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc

    # History + audit.
    db.add(
        JobCodeVersion(
            job_id=job.id,
            script_path=job.script_path or "",
            backup_path=result["backup_path"],
            content_hash_before=result["content_hash_before"],
            content_hash_after=result["content_hash_after"],
            changed_by=user.email,
            change_summary=payload.change_summary,
            size_before_bytes=result["size_before_bytes"],
            size_after_bytes=result["size_after_bytes"],
        )
    )
    record_audit(
        db,
        action="JOB_CODE_UPDATED",
        user=user,
        entity_type="job",
        entity_id=job.id,
        detail={
            "script_path": job.script_path,
            "backup_path": result["backup_path"],
            "size_after_bytes": result["size_after_bytes"],
        },
    )
    job.updated_by = user.email
    db.commit()

    try:
        return _code_out(db, job, user)
    except CodeError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
