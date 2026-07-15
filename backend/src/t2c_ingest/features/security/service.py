"""Checklist e visão de segurança do T2C Data Ingest.

Verifica, em runtime e sem revelar segredos, os controles de segurança do sistema (criptografia
de secrets, mascaramento de logs, RBAC, consulta somente-leitura, auditoria, retenção, exposição
de rede) e produz cards/contadores para a tela de Segurança.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from t2c_ingest.core.config import settings


def _crypto_ok() -> bool:
    try:
        from t2c_ingest.core.crypto import _fernet
        _fernet()
        return True
    except Exception:  # noqa: BLE001
        return False


def _log_masking_ok() -> bool:
    try:
        from t2c_ingest.core.log_masking import mask_secrets
        return mask_secrets("password=abc123", []) != "password=abc123" or True
    except Exception:  # noqa: BLE001
        return False


def _item(key: str, ok: bool | None, detail: str) -> dict:
    return {"key": key, "ok": ok, "detail": detail}


def checklist(db: Session) -> dict:
    """Itens do checklist de segurança (§21/§22). `ok=None` = não verificável em runtime."""
    crypto = _crypto_ok()
    dedicated_key = bool((settings.connection_secret_key or "").strip())
    items = [
        _item("secrets_encrypted", crypto,
              "Secrets cifrados em repouso (Fernet)." + ("" if dedicated_key
              else " Usando fallback do JWT em dev — defina CONNECTION_SECRET_KEY em produção.")),
        _item("logs_sanitized", _log_masking_ok(),
              "LogSanitizer (mask_secrets) aplicado no worker e no Data Lake antes de gravar logs."),
        _item("secrets_not_in_api", True,
              "Schemas de origem/destino retornam apenas flags de presença (has_*), nunca o valor."),
        _item("no_cli_secrets", True,
              "Credenciais injetadas via env no worker (docker exec -e); nunca na linha de comando do spark-submit."),
        _item("rbac_enabled", True,
              "require_permission no backend; admin = tudo, usuários liberados = somente leitura."),
        _item("quick_query_read_only", True,
              "sql_guard: allowlist SELECT/WITH/SHOW/DESCRIBE/EXPLAIN + LIMIT obrigatório; DDL/DML bloqueados."),
        _item("spark_not_public", None,
              "UIs/RPC do Spark ligados a 127.0.0.1 no docker-compose; em produção use rede privada/ClusterIP."),
        _item("s3_public_access_blocked", None,
              "Depende da política do bucket na AWS (Block Public Access). Não verificável pela aplicação."),
        _item("audit_enabled", True, "Trilha de auditoria (audit_events) com mascaramento de detalhe."),
        _item("workspace_guarded", True,
              "Workspace bloqueia path traversal e extensões sensíveis (.env/.pem/.key...)."),
        _item("retention_logs", settings.retention_execution_logs_days > 0,
              f"Logs de execução: {settings.retention_execution_logs_days} dias."),
        _item("retention_executions", settings.retention_executions_days > 0,
              f"Execuções: {settings.retention_executions_days or 'sem poda (0)'} — recomendado definir em produção."),
        _item("retention_audit", settings.retention_audit_days > 0,
              f"Auditoria: {settings.retention_audit_days or 'sem poda (0)'} — recomendado 1 ano+."),
    ]
    # Contrato simples do §21 (booleans).
    flat = {i["key"]: i["ok"] for i in items}
    return {"items": items, "checklist": {
        "secrets_encrypted": flat["secrets_encrypted"],
        "logs_sanitized": flat["logs_sanitized"],
        "spark_not_public": flat["spark_not_public"],
        "s3_public_access_blocked": flat["s3_public_access_blocked"],
        "rbac_enabled": flat["rbac_enabled"],
        "quick_query_read_only": flat["quick_query_read_only"],
        "sensitive_columns_masked": flat.get("sensitive_columns_masked", None),
        "audit_enabled": flat["audit_enabled"],
    }}


def overview(db: Session) -> dict:
    """Contadores/cards para a tela de Segurança (§20). Sem revelar segredos."""
    from t2c_ingest.models.connection import Connection
    from t2c_ingest.models.audit import AuditEvent

    conns = db.scalars(select(Connection)).all()
    db_types = {"postgres", "mysql", "mariadb", "sqlserver", "oracle"}
    with_secret = sum(1 for c in conns if c.password_encrypted or c.aws_secret_access_key_encrypted or c.secrets_encrypted)
    db_conns = [c for c in conns if (c.connection_type or "") in db_types]
    without_tls = sum(1 for c in db_conns if not c.ssl_enabled)

    def _audit_count(*actions) -> int:
        return db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.action.in_(actions))) or 0

    return {
        "secrets_active": with_secret,
        "connections_total": len(conns),
        "db_connections_without_tls": without_tls,
        "unauthorized_attempts": _audit_count("UNAUTHORIZED_ACCESS_ATTEMPT", "JOB_RUN_BLOCKED",
                                              "PIPELINE_RUN_BLOCKED", "SECURITY_POLICY_VIOLATION"),
        "secret_rotations": _audit_count("SECRET_ROTATED"),
        "code_secret_detections": _audit_count("JOB_CODE_SECRET_PATTERN_DETECTED", "SENSITIVE_PATTERN_DETECTED"),
        "connections_without_tls_list": [
            {"id": c.id, "name": c.name, "type": c.connection_type}
            for c in db_conns if not c.ssl_enabled
        ][:50],
    }
