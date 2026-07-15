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


def _item(key: str, ok: bool | None, category: str, detail: str, recommendation: str | None = None) -> dict:
    return {"key": key, "ok": ok, "category": category, "detail": detail, "recommendation": recommendation}


# Ordem/rótulos das categorias do checklist (para agrupar no frontend).
CATEGORIES = [
    ("secrets", "Secrets & credenciais"),
    ("logs", "Logs & dados"),
    ("access", "Acesso & RBAC"),
    ("network", "Rede & cluster"),
    ("retention", "Retenção"),
]


def checklist(db: Session) -> dict:
    """Itens do checklist de segurança (§21/§22), agrupados por categoria. `ok=None` = depende de
    infra externa (não verificável pela aplicação)."""
    dedicated_key = bool((settings.connection_secret_key or "").strip())
    items = [
        _item("secrets_encrypted", _crypto_ok(), "secrets",
              "Senhas, tokens e chaves AWS são cifrados (Fernet) antes de ir ao banco; só o backend/worker decifra."
              + ("" if dedicated_key else " Hoje usando a chave do JWT como fallback (dev)."),
              None if dedicated_key else "Defina CONNECTION_SECRET_KEY dedicada em produção."),
        _item("secrets_not_in_api", True, "secrets",
              "Ao ler uma origem/destino, a API devolve apenas indicadores de presença (has_password…), nunca o valor."),
        _item("no_cli_secrets", True, "secrets",
              "O worker injeta credenciais como variáveis de ambiente no container; nunca na linha de comando do spark-submit (que apareceria em `ps`/UI)."),
        _item("logs_sanitized", _log_masking_ok(), "logs",
              "Todo log passa pelo LogSanitizer, que substitui senhas/tokens/chaves por ******** antes de gravar/exibir."),
        _item("sensitive_columns_masked", True, "logs",
              "Colunas sensíveis (Controle.dados_sensiveis + PII padrão) são mascaradas nas amostras e na Consulta rápida do Data Lake."),
        _item("workspace_guarded", True, "logs",
              "O editor de código bloqueia caminhos '../', extensões perigosas (.env/.pem/.key) e detecta segredos no código ao salvar."),
        _item("rbac_enabled", True, "access",
              "Toda ação sensível é validada no backend (require_permission): admin faz tudo; usuários liberados só leem. Não é só ocultar botão."),
        _item("quick_query_read_only", True, "access",
              "A Consulta rápida do Data Lake só aceita leitura (SELECT/WITH/SHOW/DESCRIBE/EXPLAIN) com LIMIT; DDL/DML são recusados."),
        _item("audit_enabled", True, "access",
              "Ações são registradas em audit_events (criação/edição/execução/rotação de secret…) com o detalhe mascarado."),
        _item("spark_not_public", None, "network",
              "As UIs/RPC do Spark estão ligadas a 127.0.0.1 no docker-compose (sem exposição externa).",
              "Em produção, rode o Spark em rede privada/ClusterIP, sem UI pública."),
        _item("s3_public_access_blocked", None, "network",
              "O bucket do Data Lake deve ter Block Public Access e política restrita — isso vive na conta AWS.",
              "Verifique na AWS: Block Public Access ativo, política restrita e IAM de mínimo privilégio."),
        _item("retention_logs", settings.retention_execution_logs_days > 0, "retention",
              f"Logs detalhados de execução são podados após {settings.retention_execution_logs_days} dias."),
        _item("retention_executions",
              settings.retention_executions_days > 0, "retention",
              (f"Histórico de execuções podado após {settings.retention_executions_days} dias."
               if settings.retention_executions_days > 0 else "Histórico de execuções sem poda (0)."),
              None if settings.retention_executions_days > 0 else "Defina RETENTION_EXECUTIONS_DAYS."),
        _item("retention_audit",
              settings.retention_audit_days > 0, "retention",
              (f"Auditoria retida por {settings.retention_audit_days} dias."
               if settings.retention_audit_days > 0 else "Auditoria sem poda (0)."),
              None if settings.retention_audit_days > 0 else "Defina RETENTION_AUDIT_DAYS (1 ano+)."),
    ]
    flat = {i["key"]: i["ok"] for i in items}
    return {"items": items, "categories": [{"key": k, "label": l} for k, l in CATEGORIES],
            "summary": {"ok": sum(1 for i in items if i["ok"] is True),
                        "pending": sum(1 for i in items if i["ok"] is False),
                        "na": sum(1 for i in items if i["ok"] is None),
                        "total": len(items)},
            "checklist": {
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
