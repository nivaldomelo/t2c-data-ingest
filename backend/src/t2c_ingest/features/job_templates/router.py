from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.job_templates import service
from t2c_ingest.services.audit import record_audit

router = APIRouter(prefix="/job-templates", tags=["job-templates"])


class TemplateJobMeta(BaseModel):
    name: str = ""
    description: str | None = None
    engine: str | None = None
    job_type: str | None = None


class TemplatePreviewIn(BaseModel):
    template_id: str
    job: TemplateJobMeta = TemplateJobMeta()
    control_id: int | None = None
    parameters: dict | None = None


@router.get("")
def list_job_templates(
    _: CurrentUser = Depends(require_permission(perms.INGEST_JOBS_CREATE)),
) -> list[dict]:
    return service.list_templates()


@router.get("/{template_id}")
def get_job_template(
    template_id: str,
    _: CurrentUser = Depends(require_permission(perms.INGEST_JOBS_CREATE)),
) -> dict:
    try:
        return service.get_template(template_id)
    except service.TemplateError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message)


@router.post("/preview")
def preview_job_template(
    payload: TemplatePreviewIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_JOBS_CREATE)),
) -> dict:
    try:
        files = service.preview(db, payload.template_id, payload.job.model_dump(), payload.control_id)
    except service.TemplateError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message)
    record_audit(db, action="JOB_TEMPLATE_PREVIEWED", user=user, entity_type="job_template",
                 entity_id=None, detail={"template_id": payload.template_id, "control_id": payload.control_id,
                                         "files": [f["path"] for f in files]})
    db.commit()
    return {"files": files}
