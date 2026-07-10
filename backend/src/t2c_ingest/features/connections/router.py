from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from t2c_ingest.core.crypto import encrypt_secret
from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.connections import s3_service
from t2c_ingest.features.connections.service import test_connection
from t2c_ingest.models.connection import DEFAULT_PORTS, Connection
from t2c_ingest.schemas.connection import (
    ConnectionCreate,
    ConnectionOut,
    ConnectionSummary,
    ConnectionTestResult,
    ConnectionUpdate,
    S3ObjectsOut,
    S3TestResult,
)
from t2c_ingest.services.audit import record_audit

router = APIRouter(prefix="/connections", tags=["connections"])


def _to_out(conn: Connection) -> ConnectionOut:
    out = ConnectionOut.model_validate(conn)
    out.has_password = bool(conn.password_encrypted)
    out.has_aws_access_key = bool(conn.aws_access_key_id_encrypted)
    out.has_aws_secret_key = bool(conn.aws_secret_access_key_encrypted)
    out.has_aws_session_token = bool(conn.aws_session_token_encrypted)
    return out


# Map write-only AWS secret fields (create/update payload) -> encrypted columns on the model.
_AWS_SECRET_FIELDS = {
    "aws_access_key_id": "aws_access_key_id_encrypted",
    "aws_secret_access_key": "aws_secret_access_key_encrypted",
    "aws_session_token": "aws_session_token_encrypted",
}


def _apply_aws_secrets(conn: Connection, payload) -> None:
    """Encrypt+store any provided AWS secret; empty/omitted keeps the current value."""
    for field, column in _AWS_SECRET_FIELDS.items():
        value = getattr(payload, field, None)
        if value:
            setattr(conn, column, encrypt_secret(value))


@router.get("/summary", response_model=ConnectionSummary)
def summary(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_CONNECTIONS_READ)),
) -> ConnectionSummary:
    def _count(*where) -> int:
        stmt = select(func.count(Connection.id))
        for w in where:
            stmt = stmt.where(w)
        return db.scalar(stmt) or 0

    return ConnectionSummary(
        total=_count(),
        postgres=_count(Connection.connection_type == "postgres"),
        mysql=_count(Connection.connection_type == "mysql"),
        s3=_count(Connection.connection_type == "s3"),
        test_success=_count(Connection.last_test_status == "success"),
        test_failed=_count(Connection.last_test_status == "failed"),
    )


@router.get("", response_model=PageOut[ConnectionOut])
def list_connections(
    params: PageParams = Depends(),
    connection_type: str | None = None,
    last_test_status: str | None = None,
    active: bool | None = None,
    q: str | None = Query(None, description="Busca por nome, host ou banco"),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_CONNECTIONS_READ)),
) -> PageOut[ConnectionOut]:
    stmt = select(Connection)
    count_stmt = select(func.count(Connection.id))
    filters = []
    if connection_type:
        filters.append(Connection.connection_type == connection_type)
    if last_test_status:
        filters.append(Connection.last_test_status == last_test_status)
    if active is not None:
        filters.append(Connection.active == active)
    if q:
        like = f"%{q.strip()}%"
        filters.append(
            or_(
                Connection.name.ilike(like),
                Connection.host.ilike(like),
                Connection.database_name.ilike(like),
            )
        )
    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(Connection.name).offset(params.offset).limit(params.limit)
    ).all()
    return PageOut.build([_to_out(r) for r in rows], total, params)


@router.post("", response_model=ConnectionOut, status_code=status.HTTP_201_CREATED)
def create_connection(
    payload: ConnectionCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_CONNECTIONS_WRITE)),
) -> ConnectionOut:
    if db.scalar(select(Connection).where(Connection.name == payload.name)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Já existe uma conexão com esse nome")
    data = payload.model_dump(exclude={"password", *_AWS_SECRET_FIELDS})
    if data.get("port") is None:
        data["port"] = DEFAULT_PORTS.get(payload.connection_type)
    conn = Connection(**data, created_by=user.email, updated_by=user.email)
    if payload.password:
        conn.password_encrypted = encrypt_secret(payload.password)
    _apply_aws_secrets(conn, payload)
    db.add(conn)
    db.flush()
    record_audit(db, action="ingest.connection.created", user=user, entity_type="connection", entity_id=conn.id)
    db.commit()
    db.refresh(conn)
    return _to_out(conn)


@router.get("/{connection_id}", response_model=ConnectionOut)
def get_connection(
    connection_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_CONNECTIONS_READ)),
) -> ConnectionOut:
    conn = db.get(Connection, connection_id)
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conexão não encontrada")
    return _to_out(conn)


@router.put("/{connection_id}", response_model=ConnectionOut)
def update_connection(
    connection_id: int,
    payload: ConnectionUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_CONNECTIONS_WRITE)),
) -> ConnectionOut:
    conn = db.get(Connection, connection_id)
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conexão não encontrada")
    data = payload.model_dump(exclude_unset=True, exclude={"password", *_AWS_SECRET_FIELDS})
    for key, value in data.items():
        setattr(conn, key, value)
    # Empty/omitted secrets keep the current ones; non-empty values replace them.
    if payload.password:
        conn.password_encrypted = encrypt_secret(payload.password)
    _apply_aws_secrets(conn, payload)
    conn.updated_by = user.email
    record_audit(db, action="ingest.connection.updated", user=user, entity_type="connection", entity_id=conn.id)
    db.commit()
    db.refresh(conn)
    return _to_out(conn)


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    connection_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_CONNECTIONS_DELETE)),
) -> None:
    conn = db.get(Connection, connection_id)
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conexão não encontrada")
    record_audit(db, action="ingest.connection.deleted", user=user, entity_type="connection", entity_id=conn.id)
    db.delete(conn)
    db.commit()


@router.post("/{connection_id}/test", response_model=ConnectionTestResult)
def test(
    connection_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_CONNECTIONS_TEST)),
) -> ConnectionTestResult:
    conn = db.get(Connection, connection_id)
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conexão não encontrada")
    if conn.connection_type == "s3":
        result = s3_service.test_connection(conn)
        ok, message = result["success"], result["message"]
    else:
        ok, message = test_connection(conn)
    now = datetime.now(timezone.utc)
    conn.last_test_status = "success" if ok else "failed"
    conn.last_test_message = message
    conn.last_tested_at = now
    record_audit(
        db,
        action="ingest.connection.tested",
        user=user,
        entity_type="connection",
        entity_id=conn.id,
        detail={"status": conn.last_test_status},
    )
    if not ok:
        from t2c_ingest.features.alerts.service import emit

        emit(db, event_type="CONNECTION_FAILED", severity="warning",
             title=f"Conexão falhou: {conn.name}",
             message=f"Teste da conexão '{conn.name}' ({conn.connection_type}) falhou: {message}"[:1000])
    db.commit()
    return ConnectionTestResult(status=conn.last_test_status, message=message, tested_at=now)


# ── S3 / Data Lake object access via a connection ──
def _require_s3(db: Session, connection_id: int) -> Connection:
    conn = db.get(Connection, connection_id)
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conexão não encontrada")
    if conn.connection_type != "s3":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conexão não é do tipo S3.")
    return conn


@router.get("/{connection_id}/s3/objects", response_model=S3ObjectsOut)
def s3_objects(
    connection_id: int,
    prefix: str | None = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_S3_LIST)),
) -> S3ObjectsOut:
    conn = _require_s3(db, connection_id)
    try:
        return S3ObjectsOut(**s3_service.list_objects(conn, prefix=prefix, limit=limit))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Falha ao listar objetos: {type(exc).__name__}") from exc


@router.get("/{connection_id}/s3/prefixes", response_model=S3ObjectsOut)
def s3_prefixes(
    connection_id: int,
    prefix: str | None = Query(None),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_S3_LIST)),
) -> S3ObjectsOut:
    conn = _require_s3(db, connection_id)
    try:
        return S3ObjectsOut(**s3_service.list_objects(conn, prefix=prefix, limit=200))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Falha ao listar prefixos: {type(exc).__name__}") from exc


@router.post("/{connection_id}/s3/test-read", response_model=S3TestResult)
def s3_test_read(
    connection_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_S3_READ)),
) -> S3TestResult:
    conn = _require_s3(db, connection_id)
    return S3TestResult(**s3_service.test_connection(conn, attempt_write=False))


@router.post("/{connection_id}/s3/test-write", response_model=S3TestResult)
def s3_test_write(
    connection_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_S3_WRITE)),
) -> S3TestResult:
    conn = _require_s3(db, connection_id)
    if not conn.can_write:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conexão S3 não tem escrita habilitada.")
    result = s3_service.test_connection(conn, attempt_write=True)
    record_audit(db, action="S3_TEST_WRITE_SUCCEEDED" if result["success"] else "S3_TEST_WRITE_FAILED",
                 user=user, entity_type="connection", entity_id=conn.id,
                 detail={"can_write": result["details"].get("can_write")})
    db.commit()
    return S3TestResult(**result)
