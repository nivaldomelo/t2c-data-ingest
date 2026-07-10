from __future__ import annotations

import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from t2c_ingest.core.config import settings
from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.clusters import state as cluster_state
from t2c_ingest.models.cluster import Cluster
from t2c_ingest.schemas.cluster import (
    ClusterConnectionResult,
    ClusterCreate,
    ClusterOut,
    ClustersSummary,
    ClusterUpdate,
    ClusterValidationOut,
    ClusterWorker,
    ClusterWorkersOut,
)
from t2c_ingest.services.audit import record_audit

router = APIRouter(prefix="/clusters", tags=["clusters"])
cv_router = APIRouter(prefix="/cluster-validations", tags=["clusters"])

_ENV_LABEL = {"local": "Local Docker", "local_docker": "Local Docker", "kubernetes": "Kubernetes",
              "eks": "AWS EKS", "emr": "AWS EMR"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _environment(cluster: Cluster) -> str:
    return cluster.environment or ("local" if cluster.type == "local_docker" else cluster.type)


def _enrich(cluster: Cluster, summ: dict, persist: bool) -> ClusterOut:
    """Overlay live master data onto a cluster row (persisting the counters when reachable)."""
    if summ.get("reachable"):
        cluster.worker_count = summ["workers"]
        cluster.total_cores = summ["cores"]
        cluster.total_memory = summ["memory"] or cluster.total_memory
        cluster.last_checked_at = _now()
        cluster.last_heartbeat_at = _now()
        cluster.status = "active" if cluster.is_active else "inactive"
    elif persist and cluster.is_active:
        cluster.status = "unreachable"
    out = ClusterOut.model_validate(cluster)
    env = _environment(cluster)
    out.environment = env
    out.environment_label = _ENV_LABEL.get(env, env)
    out.live = bool(summ.get("reachable"))
    return out


@router.get("/summary", response_model=ClustersSummary)
def clusters_summary(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_CLUSTERS_READ)),
) -> ClustersSummary:
    clusters = db.scalars(select(Cluster)).all()
    summ = cluster_state.summarize(cluster_state.fetch_master_state())
    last_val = next((c.last_validation_status for c in clusters if c.last_validation_status), None)
    return ClustersSummary(
        total_clusters=len(clusters),
        active_clusters=len([c for c in clusters if c.is_active]),
        workers_total=summ.get("workers", 0),
        cores_total=summ.get("cores", 0),
        memory_total=summ.get("memory"),
        last_validation_status=last_val,
    )


@router.get("", response_model=PageOut[ClusterOut])
def list_clusters(
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_CLUSTERS_READ)),
) -> PageOut[ClusterOut]:
    total = db.scalar(select(func.count(Cluster.id))) or 0
    rows = db.scalars(
        select(Cluster).order_by(Cluster.name).offset(params.offset).limit(params.limit)
    ).all()
    summ = cluster_state.summarize(cluster_state.fetch_master_state())
    items = [_enrich(c, summ, persist=False) for c in rows]
    db.rollback()  # live overlay is response-only — never write on a GET
    return PageOut.build(items, total, params)


@router.post("", response_model=ClusterOut, status_code=status.HTTP_201_CREATED)
def create_cluster(
    payload: ClusterCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_CLUSTERS_MANAGE)),
) -> ClusterOut:
    if db.scalar(select(Cluster).where(Cluster.name == payload.name)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cluster name already exists")
    cluster = Cluster(**payload.model_dump(), created_by=user.email)
    db.add(cluster)
    db.flush()
    record_audit(db, action="CLUSTER_CREATED", user=user, entity_type="cluster", entity_id=cluster.id)
    db.commit()
    db.refresh(cluster)
    return _enrich(cluster, {"reachable": False}, persist=False)


@router.get("/{cluster_id}", response_model=ClusterOut)
def get_cluster(
    cluster_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_CLUSTERS_READ)),
) -> ClusterOut:
    cluster = db.get(Cluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    summ = cluster_state.summarize(cluster_state.fetch_master_state())
    out = _enrich(cluster, summ, persist=False)
    db.rollback()  # live overlay is response-only — never write on a GET
    return out


@router.patch("/{cluster_id}", response_model=ClusterOut)
def update_cluster(
    cluster_id: int,
    payload: ClusterUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_CLUSTERS_MANAGE)),
) -> ClusterOut:
    cluster = db.get(Cluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(cluster, key, value)
    record_audit(db, action="CLUSTER_UPDATED", user=user, entity_type="cluster", entity_id=cluster.id)
    db.commit()
    db.refresh(cluster)
    return _enrich(cluster, {"reachable": False}, persist=False)


@router.get("/{cluster_id}/workers", response_model=ClusterWorkersOut)
def cluster_workers(
    cluster_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_CLUSTERS_READ)),
) -> ClusterWorkersOut:
    cluster = db.get(Cluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    workers = cluster_state.list_workers(cluster_state.fetch_master_state())
    detected = len([w for w in workers if w["status"] == "active"])
    return ClusterWorkersOut(
        cluster_id=cluster.id,
        workers_expected=cluster.expected_workers or settings.spark_expected_workers,
        workers_detected=detected,
        workers=[ClusterWorker(**w) for w in workers],
    )


def _ping_master(master: str) -> tuple[bool, str]:
    parsed = urlparse(master if "//" in master else f"spark://{master}")
    host, port = parsed.hostname, parsed.port or 7077
    if not host:
        return False, "Nenhuma URL de master configurada."
    try:
        with socket.create_connection((host, port), timeout=3):
            return True, "Spark master acessível."
    except OSError as exc:
        return False, f"Inacessível: {exc}"


@router.post("/{cluster_id}/test", response_model=ClusterConnectionResult)
@router.post("/{cluster_id}/test-connection", response_model=ClusterConnectionResult)
def test_connection(
    cluster_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_CLUSTERS_TEST)),
) -> ClusterConnectionResult:
    cluster = db.get(Cluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    record_audit(db, action="CLUSTER_TEST_STARTED", user=user, entity_type="cluster", entity_id=cluster.id)
    reachable, message = _ping_master(cluster.spark_master_url or "")
    summ = cluster_state.summarize(cluster_state.fetch_master_state()) if reachable else {"reachable": False}
    _enrich(cluster, summ, persist=True)
    record_audit(db, action="CLUSTER_TEST_SUCCEEDED" if reachable else "CLUSTER_TEST_FAILED",
                 user=user, entity_type="cluster", entity_id=cluster.id, detail={"message": message})
    if not reachable:
        from t2c_ingest.features.alerts.service import emit

        emit(db, event_type="CLUSTER_UNAVAILABLE", severity="critical",
             title=f"Cluster indisponível: {cluster.name}",
             message=f"Spark master ({cluster.spark_master_url}) inacessível: {message}"[:1000])
    db.commit()
    return ClusterConnectionResult(reachable=reachable, master_url=cluster.spark_master_url, message=message,
                                   workers_detected=summ.get("workers") if reachable else None)


@router.post("/{cluster_id}/validate-workers", response_model=ClusterWorkersOut)
def validate_workers(
    cluster_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_CLUSTERS_VALIDATE)),
) -> ClusterWorkersOut:
    cluster = db.get(Cluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    workers = cluster_state.list_workers(cluster_state.fetch_master_state())
    detected = len([w for w in workers if w["status"] == "active"])
    expected = cluster.expected_workers or settings.spark_expected_workers
    cluster.last_checked_at = _now()
    cluster.last_validation_status = "success" if detected >= expected else "failed"
    record_audit(db, action="CLUSTER_WORKERS_VALIDATED", user=user, entity_type="cluster", entity_id=cluster.id,
                 detail={"expected": expected, "detected": detected})
    db.commit()
    return ClusterWorkersOut(cluster_id=cluster.id, workers_expected=expected, workers_detected=detected,
                             workers=[ClusterWorker(**w) for w in workers])


def _enqueue_runtime_validation(db: Session, user: CurrentUser, vtype: str) -> ClusterValidationOut:
    from t2c_ingest.models.runtime import RuntimeLibrary, RuntimeValidation

    libs = None
    if vtype == "libraries":
        libs = [lib.package_name for lib in db.scalars(select(RuntimeLibrary).where(RuntimeLibrary.active.is_(True))).all()]
    val = RuntimeValidation(
        validation_type=vtype, status="queued",
        worker_count_expected=settings.spark_expected_workers, libraries_checked=libs, created_by=user.email,
    )
    db.add(val)
    db.commit()
    db.refresh(val)
    return ClusterValidationOut(
        id=val.id, validation_type=val.validation_type, status=val.status,
        worker_count_expected=val.worker_count_expected, worker_count_detected=val.worker_count_detected,
        started_at=val.started_at, finished_at=val.finished_at, created_at=val.created_at,
    )


@router.post("/{cluster_id}/validate-libraries", response_model=ClusterValidationOut, status_code=status.HTTP_201_CREATED)
def validate_libraries(
    cluster_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_CLUSTERS_VALIDATE)),
) -> ClusterValidationOut:
    if not db.get(Cluster, cluster_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    record_audit(db, action="CLUSTER_LIBRARIES_VALIDATED", user=user, entity_type="cluster", entity_id=cluster_id)
    return _enqueue_runtime_validation(db, user, "libraries")


@router.post("/{cluster_id}/validate-distributed-execution", response_model=ClusterValidationOut, status_code=status.HTTP_201_CREATED)
def validate_distributed(
    cluster_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_CLUSTERS_VALIDATE)),
) -> ClusterValidationOut:
    if not db.get(Cluster, cluster_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    record_audit(db, action="CLUSTER_DISTRIBUTED_EXECUTION_VALIDATED", user=user, entity_type="cluster", entity_id=cluster_id)
    return _enqueue_runtime_validation(db, user, "distributed")


@router.get("/{cluster_id}/validations", response_model=list[ClusterValidationOut])
def cluster_validations(
    cluster_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_CLUSTERS_READ)),
) -> list[ClusterValidationOut]:
    from t2c_ingest.models.runtime import RuntimeValidation

    if not db.get(Cluster, cluster_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    rows = db.scalars(select(RuntimeValidation).order_by(RuntimeValidation.id.desc()).limit(30)).all()
    return [ClusterValidationOut(
        id=r.id, validation_type=r.validation_type, status=r.status,
        worker_count_expected=r.worker_count_expected, worker_count_detected=r.worker_count_detected,
        started_at=r.started_at, finished_at=r.finished_at, created_at=r.created_at,
    ) for r in rows]


@cv_router.get("/{validation_id}/logs")
def validation_logs(
    validation_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_LOGS_READ)),
) -> dict:
    from t2c_ingest.models.runtime import RuntimeValidation

    row = db.get(RuntimeValidation, validation_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation not found")
    return {"id": row.id, "status": row.status, "type": row.validation_type,
            "workers_result": row.workers_result, "logs": row.logs or ""}
