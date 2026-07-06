from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.models.airflow import AirflowDagImport, AirflowTaskImport
from t2c_ingest.schemas.airflow import AirflowDagCreate, AirflowDagOut, AirflowDagUpdate
from t2c_ingest.services.audit import record_audit

router = APIRouter(prefix="/airflow", tags=["airflow_migration"])


def _load(db: Session, dag_id: int) -> AirflowDagImport:
    dag = db.scalar(
        select(AirflowDagImport)
        .options(selectinload(AirflowDagImport.tasks))
        .where(AirflowDagImport.id == dag_id)
    )
    if not dag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DAG import not found")
    return dag


@router.get("/dags", response_model=PageOut[AirflowDagOut])
def list_dags(
    params: PageParams = Depends(),
    migration_status: str | None = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_AIRFLOW_READ)),
) -> PageOut[AirflowDagOut]:
    stmt = select(AirflowDagImport).options(selectinload(AirflowDagImport.tasks))
    count_stmt = select(func.count(AirflowDagImport.id))
    if migration_status:
        stmt = stmt.where(AirflowDagImport.migration_status == migration_status)
        count_stmt = count_stmt.where(AirflowDagImport.migration_status == migration_status)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(AirflowDagImport.dag_name).offset(params.offset).limit(params.limit)
    ).all()
    return PageOut.build([AirflowDagOut.model_validate(r) for r in rows], total, params)


@router.post("/dags", response_model=AirflowDagOut, status_code=status.HTTP_201_CREATED)
def create_dag(
    payload: AirflowDagCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_AIRFLOW_MIGRATE)),
) -> AirflowDagOut:
    if db.scalar(select(AirflowDagImport).where(AirflowDagImport.dag_name == payload.dag_name)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="DAG already inventoried")
    dag = AirflowDagImport(**payload.model_dump(exclude={"tasks"}), created_by=user.email)
    db.add(dag)
    db.flush()
    for task in payload.tasks:
        db.add(AirflowTaskImport(dag_import_id=dag.id, **task.model_dump()))
    record_audit(db, action="ingest.airflow.dag_inventoried", user=user, entity_type="airflow_dag", entity_id=dag.id)
    db.commit()
    return AirflowDagOut.model_validate(_load(db, dag.id))


@router.get("/dags/{dag_id}", response_model=AirflowDagOut)
def get_dag(
    dag_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_AIRFLOW_READ)),
) -> AirflowDagOut:
    return AirflowDagOut.model_validate(_load(db, dag_id))


@router.patch("/dags/{dag_id}", response_model=AirflowDagOut)
def update_dag(
    dag_id: int,
    payload: AirflowDagUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_AIRFLOW_MIGRATE)),
) -> AirflowDagOut:
    dag = _load(db, dag_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(dag, key, value)
    record_audit(db, action="ingest.airflow.dag_updated", user=user, entity_type="airflow_dag", entity_id=dag.id)
    db.commit()
    return AirflowDagOut.model_validate(_load(db, dag.id))
