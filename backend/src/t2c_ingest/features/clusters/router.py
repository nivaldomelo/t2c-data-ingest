from __future__ import annotations

import socket
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.models.cluster import Cluster
from t2c_ingest.schemas.cluster import (
    ClusterConnectionResult,
    ClusterCreate,
    ClusterOut,
    ClusterUpdate,
)
from t2c_ingest.services.audit import record_audit

router = APIRouter(prefix="/clusters", tags=["clusters"])


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
    return PageOut.build([ClusterOut.model_validate(r) for r in rows], total, params)


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
    record_audit(db, action="ingest.cluster.created", user=user, entity_type="cluster", entity_id=cluster.id)
    db.commit()
    db.refresh(cluster)
    return ClusterOut.model_validate(cluster)


@router.get("/{cluster_id}", response_model=ClusterOut)
def get_cluster(
    cluster_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_CLUSTERS_READ)),
) -> ClusterOut:
    cluster = db.get(Cluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    return ClusterOut.model_validate(cluster)


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
    record_audit(db, action="ingest.cluster.updated", user=user, entity_type="cluster", entity_id=cluster.id)
    db.commit()
    db.refresh(cluster)
    return ClusterOut.model_validate(cluster)


@router.post("/{cluster_id}/test-connection", response_model=ClusterConnectionResult)
def test_connection(
    cluster_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_CLUSTERS_READ)),
) -> ClusterConnectionResult:
    cluster = db.get(Cluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    master = cluster.spark_master_url or ""
    parsed = urlparse(master if "//" in master else f"spark://{master}")
    host, port = parsed.hostname, parsed.port or 7077
    if not host:
        return ClusterConnectionResult(reachable=False, master_url=master, message="No master URL configured")
    try:
        with socket.create_connection((host, port), timeout=3):
            return ClusterConnectionResult(reachable=True, master_url=master, message="Spark master reachable")
    except OSError as exc:
        return ClusterConnectionResult(reachable=False, master_url=master, message=f"Unreachable: {exc}")
