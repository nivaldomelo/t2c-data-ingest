from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.variables.service import (
    is_secret_variable,
    normalize_name,
    public_value,
    store_value,
    usage_examples,
)
from t2c_ingest.models.variable import Variable
from t2c_ingest.schemas.variable import (
    VariableCreate,
    VariableDetailOut,
    VariableOut,
    VariableSummary,
    VariableUpdate,
    VariableUsage,
)
from t2c_ingest.services.audit import record_audit

router = APIRouter(prefix="/variables", tags=["variables"])


def _out(var: Variable) -> VariableOut:
    out = VariableOut.model_validate(var)
    value, masked = public_value(var)
    out.value = value
    out.masked_value = masked
    out.has_value = var.value is not None
    return out


def _require_secret_write(user: CurrentUser) -> None:
    if not user.has(perms.INGEST_VARIABLES_SECRET_WRITE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissão insuficiente para gravar variáveis secretas (ingest:variables:secret:write).",
        )


@router.get("/summary", response_model=VariableSummary)
def summary(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_VARIABLES_READ)),
) -> VariableSummary:
    def _count(*where) -> int:
        stmt = select(func.count(Variable.id))
        for w in where:
            stmt = stmt.where(w)
        return db.scalar(stmt) or 0

    return VariableSummary(
        total=_count(),
        active=_count(Variable.active.is_(True)),
        secret=_count(Variable.is_secret.is_(True)),
        global_scope=_count(Variable.scope == "global"),
        with_environment=_count(Variable.environment.is_not(None)),
    )


@router.get("", response_model=PageOut[VariableOut])
def list_variables(
    params: PageParams = Depends(),
    search: str | None = None,
    name: str | None = None,
    scope: str | None = None,
    environment: str | None = None,
    variable_type: str | None = None,
    active: bool | None = None,
    is_secret: bool | None = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_VARIABLES_READ)),
) -> PageOut[VariableOut]:
    filters = []
    if name:
        filters.append(Variable.name.ilike(f"%{name}%"))
    if scope:
        filters.append(Variable.scope == scope)
    if environment:
        filters.append(Variable.environment == environment)
    if variable_type:
        filters.append(Variable.variable_type == variable_type)
    if active is not None:
        filters.append(Variable.active.is_(active))
    if is_secret is not None:
        filters.append(Variable.is_secret.is_(is_secret))
    if search:
        like = f"%{search.strip()}%"
        filters.append(or_(Variable.name.ilike(like), Variable.description.ilike(like)))
    stmt = select(Variable)
    count_stmt = select(func.count(Variable.id))
    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Variable.name).offset(params.offset).limit(params.limit)).all()
    return PageOut.build([_out(r) for r in rows], total, params)


@router.post("", response_model=VariableOut, status_code=status.HTTP_201_CREATED)
def create_variable(
    payload: VariableCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_VARIABLES_WRITE)),
) -> VariableOut:
    secret = is_secret_variable(payload.variable_type, payload.is_secret)
    if secret:
        _require_secret_write(user)
    data = payload.model_dump(exclude={"value"})
    data["name"] = normalize_name(payload.name)
    data["is_secret"] = secret
    var = Variable(**data, value=store_value(payload.value, secret=secret), created_by=user.id, updated_by=user.id)
    db.add(var)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Já existe uma variável com esse nome/escopo/ambiente.")
    record_audit(db, action="VARIABLE_SECRET_UPDATED" if secret else "VARIABLE_CREATED", user=user,
                 entity_type="variable", entity_id=var.id, detail={"name": var.name, "is_secret": secret})
    db.commit()
    db.refresh(var)
    return _out(var)


@router.get("/{variable_id}", response_model=VariableDetailOut)
def get_variable(
    variable_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_VARIABLES_READ)),
) -> VariableDetailOut:
    var = db.get(Variable, variable_id)
    if not var:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variável não encontrada")
    base = _out(var).model_dump()
    return VariableDetailOut(**base, usage=VariableUsage(**usage_examples(var.name, var.variable_type)))


@router.get("/{variable_id}/usage-examples", response_model=VariableUsage)
def variable_usage(
    variable_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_VARIABLES_READ)),
) -> VariableUsage:
    var = db.get(Variable, variable_id)
    if not var:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variável não encontrada")
    return VariableUsage(**usage_examples(var.name, var.variable_type))


@router.put("/{variable_id}", response_model=VariableOut)
def update_variable(
    variable_id: int,
    payload: VariableUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_VARIABLES_WRITE)),
) -> VariableOut:
    var = db.get(Variable, variable_id)
    if not var:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variável não encontrada")

    data = payload.model_dump(exclude_unset=True)
    # Resolve resulting secret flag.
    new_type = data.get("variable_type", var.variable_type)
    new_is_secret = data.get("is_secret", var.is_secret)
    secret = is_secret_variable(new_type, new_is_secret)

    value_provided = "value" in data and data["value"] not in (None, "")
    if secret and (value_provided or (not var.is_secret and secret)):
        _require_secret_write(user)

    if "name" in data and data["name"]:
        data["name"] = normalize_name(data["name"])
    # Handle value separately (empty keeps current, esp. for secrets).
    value_field = data.pop("value", None)
    for k, v in data.items():
        setattr(var, k, v)
    var.is_secret = secret
    if value_provided:
        var.value = store_value(value_field, secret=secret)
    elif not secret and "value" in payload.model_dump(exclude_unset=True) and value_field in (None, ""):
        # Non-secret explicitly cleared.
        var.value = None
    var.updated_by = user.id
    var.updated_at = datetime.now(timezone.utc)

    action = "VARIABLE_SECRET_UPDATED" if (secret and value_provided) else "VARIABLE_UPDATED"
    record_audit(db, action=action, user=user, entity_type="variable", entity_id=var.id,
                 detail={"name": var.name, "is_secret": secret})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Já existe uma variável com esse nome/escopo/ambiente.")
    db.refresh(var)
    return _out(var)


@router.delete("/{variable_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_variable(
    variable_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_VARIABLES_DELETE)),
) -> None:
    var = db.get(Variable, variable_id)
    if not var:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variável não encontrada")
    record_audit(db, action="VARIABLE_DELETED", user=user, entity_type="variable", entity_id=var.id, detail={"name": var.name})
    db.delete(var)
    db.commit()


@router.post("/{variable_id}/activate", response_model=VariableOut)
def activate(
    variable_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_VARIABLES_WRITE)),
) -> VariableOut:
    return _toggle(db, variable_id, True, user)


@router.post("/{variable_id}/deactivate", response_model=VariableOut)
def deactivate(
    variable_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_VARIABLES_WRITE)),
) -> VariableOut:
    return _toggle(db, variable_id, False, user)


def _toggle(db: Session, variable_id: int, active: bool, user: CurrentUser) -> VariableOut:
    var = db.get(Variable, variable_id)
    if not var:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variável não encontrada")
    var.active = active
    var.updated_by = user.id
    var.updated_at = datetime.now(timezone.utc)
    record_audit(db, action="VARIABLE_ACTIVATED" if active else "VARIABLE_DEACTIVATED",
                 user=user, entity_type="variable", entity_id=var.id)
    db.commit()
    db.refresh(var)
    return _out(var)
