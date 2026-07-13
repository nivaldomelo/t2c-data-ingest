"""Connector registry — the single, serializable source of truth for connection types.

Both the backend (create/update mapping + validation) and the frontend (dynamic form) consume
this, so adding a new connector is a matter of adding an entry here (plus a test function in
``connectors``) — nothing is hardcoded in the form.

Field.store tells where a value is persisted (kept backward-compatible with existing columns):
  - "col:<attr>"  -> Connection.<attr>            (host, port, database_name, username, schema_name)
  - "password"    -> Connection.password_encrypted (Fernet)
  - "aws:<which>" -> Connection.aws_*_encrypted    (access_key_id | secret_access_key | session_token)
  - "secret"      -> Connection.secrets_encrypted blob, under key = field name (Fernet)
  - "extra"       -> Connection.extra_params[field name]  (non-secret, type-specific config)
Field.secret marks values never returned by the API / masked in logs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field as dc_field


@dataclass
class Field:
    name: str
    label: str
    kind: str = "text"           # text | number | password | select | checkbox | textarea
    store: str = "extra"         # see module docstring
    secret: bool = False
    required: bool = False
    placeholder: str = ""
    help: str = ""
    section: str = "Conexão"
    options: list[str] = dc_field(default_factory=list)
    default: object = None
    show_if: dict | None = None   # {"field": "auth_type", "in": ["bearer_token"]}


@dataclass
class Connector:
    type: str
    category: str
    label: str
    default_port: int | None = None
    description: str = ""
    test_hint: str = ""
    fields: list[Field] = dc_field(default_factory=list)


# ── Common field groups ────────────────────────────────────────────────────────
def _db_fields(*, default_port: int, with_schema: bool = True, with_ssl: bool = True) -> list[Field]:
    fs = [
        Field("host", "Host", store="col:host", required=True, placeholder="db.empresa.com"),
        Field("port", "Porta", kind="number", store="col:port", default=default_port),
        Field("database_name", "Database", store="col:database_name"),
    ]
    if with_schema:
        fs.append(Field("schema_name", "Schema", store="col:schema_name", placeholder="public"))
    fs += [
        Field("username", "Usuário", store="col:username", section="Autenticação"),
        Field("password", "Senha", kind="password", store="password", secret=True, section="Autenticação"),
    ]
    if with_ssl:
        fs.append(Field("ssl_enabled", "SSL habilitado", kind="checkbox", store="col:ssl_enabled", section="Autenticação"))
    return fs


_PERMS = [
    Field("can_read", "Permite leitura (origem)", kind="checkbox", store="col:can_read", section="Permissões", default=True),
    Field("can_write", "Permite escrita (destino)", kind="checkbox", store="col:can_write", section="Permissões", default=False),
]


REGISTRY: dict[str, Connector] = {
    "postgres": Connector(
        "postgres", "database", "PostgreSQL", 5432, "Banco relacional PostgreSQL.", "SELECT 1",
        fields=_db_fields(default_port=5432) + _PERMS,
    ),
    "mysql": Connector(
        "mysql", "database", "MySQL", 3306, "Banco relacional MySQL.", "SELECT 1",
        fields=_db_fields(default_port=3306, with_schema=False) + _PERMS,
    ),
    "mariadb": Connector(
        "mariadb", "database", "MariaDB", 3306, "Banco relacional MariaDB (compatível MySQL).", "SELECT 1",
        fields=_db_fields(default_port=3306, with_schema=False) + _PERMS,
    ),
    "sqlserver": Connector(
        "sqlserver", "database", "SQL Server", 1433, "Microsoft SQL Server via ODBC/JDBC.", "SELECT 1",
        fields=_db_fields(default_port=1433) + [
            Field("encrypt", "Encrypt", kind="checkbox", store="extra", section="Avançado", default=True),
            Field("trust_server_certificate", "Trust server certificate", kind="checkbox", store="extra", section="Avançado"),
            Field("driver", "Driver ODBC", store="extra", section="Avançado", placeholder="ODBC Driver 18 for SQL Server"),
        ] + _PERMS,
    ),
    "oracle": Connector(
        "oracle", "database", "Oracle", 1521, "Banco Oracle (service name ou SID).", "SELECT 1 FROM DUAL",
        fields=[
            Field("host", "Host", store="col:host", required=True),
            Field("port", "Porta", kind="number", store="col:port", default=1521),
            Field("service_name", "Service name", store="extra", placeholder="ORCLPDB1"),
            Field("sid", "SID (opcional)", store="extra", section="Avançado"),
            Field("schema_name", "Schema", store="col:schema_name"),
            Field("username", "Usuário", store="col:username", section="Autenticação"),
            Field("password", "Senha", kind="password", store="password", secret=True, section="Autenticação"),
        ] + _PERMS,
    ),
    "mongodb": Connector(
        "mongodb", "database", "MongoDB", 27017, "MongoDB via connection string ou host/porta.", "listDatabases",
        fields=[
            Field("connection_string", "Connection string", kind="password", store="secret", secret=True,
                  placeholder="mongodb+srv://user:pass@cluster/…", help="Pode conter credenciais — armazenada cifrada."),
            Field("host", "Host (se sem connection string)", store="col:host", section="Avançado"),
            Field("port", "Porta", kind="number", store="col:port", default=27017, section="Avançado"),
            Field("database_name", "Database", store="col:database_name"),
            Field("auth_source", "Auth source", store="extra", section="Autenticação", placeholder="admin"),
            Field("username", "Usuário", store="col:username", section="Autenticação"),
            Field("password", "Senha", kind="password", store="password", secret=True, section="Autenticação"),
            Field("tls", "TLS", kind="checkbox", store="extra", section="Autenticação"),
        ] + _PERMS,
    ),
    # storage: S3 é tratado pelo fluxo dedicado existente (colunas aws_* + abas). Descrito aqui só
    # para o seletor de tipo; o formulário S3 continua sendo o específico.
    "s3": Connector(
        "s3", "storage", "AWS S3 / Data Lake", None, "Data Lake / storage no Amazon S3 (ou compatível).",
        "HeadBucket + ListObjects", fields=[],
    ),
    "rest_api": Connector(
        "rest_api", "api", "REST API Genérica", None, "Conector genérico para APIs REST.",
        "GET no endpoint de teste configurado",
        fields=[
            Field("base_url", "Base URL", store="extra", required=True, placeholder="https://api.exemplo.com"),
            Field("default_method", "Método padrão", kind="select", store="extra", options=["GET", "POST"], default="GET", section="Avançado"),
            Field("default_headers", "Headers padrão (JSON)", kind="textarea", store="extra", section="Avançado", placeholder='{"Accept": "application/json"}'),
            Field("test_endpoint", "Endpoint de teste", store="extra", placeholder="/health", section="Teste"),
            Field("timeout", "Timeout (s)", kind="number", store="extra", default=30, section="Avançado"),
            Field("auth_type", "Tipo de autenticação", kind="select", store="extra", section="Autenticação",
                  options=["none", "api_key_header", "api_key_query", "bearer_token", "basic_auth", "custom_header"], default="none"),
            # Campos condicionais por auth_type:
            Field("api_key_name", "Nome do header/param", store="extra", section="Autenticação",
                  placeholder="x-api-key", show_if={"field": "auth_type", "in": ["api_key_header", "api_key_query"]}),
            Field("api_key", "API Key", kind="password", store="secret", secret=True, section="Autenticação",
                  show_if={"field": "auth_type", "in": ["api_key_header", "api_key_query"]}),
            Field("access_token", "Access token", kind="password", store="secret", secret=True, section="Autenticação",
                  show_if={"field": "auth_type", "in": ["bearer_token"]}),
            Field("username", "Usuário", store="col:username", section="Autenticação",
                  show_if={"field": "auth_type", "in": ["basic_auth"]}),
            Field("password", "Senha", kind="password", store="password", secret=True, section="Autenticação",
                  show_if={"field": "auth_type", "in": ["basic_auth"]}),
            Field("custom_header_name", "Nome do header", store="extra", section="Autenticação",
                  show_if={"field": "auth_type", "in": ["custom_header"]}),
            Field("custom_header_value", "Valor do header", kind="password", store="secret", secret=True, section="Autenticação",
                  show_if={"field": "auth_type", "in": ["custom_header"]}),
        ] + _PERMS,
    ),
    "jira": Connector(
        "jira", "api", "Jira", None, "Jira Cloud via API (basic + API token).",
        "GET /rest/api/3/myself",
        fields=[
            Field("base_url", "Site URL", store="extra", required=True, placeholder="https://empresa.atlassian.net"),
            Field("username", "E-mail do usuário", store="col:username", required=True, section="Autenticação", placeholder="usuario@empresa.com"),
            Field("api_token", "API Token", kind="password", store="secret", secret=True, required=True, section="Autenticação"),
            Field("api_version", "Versão da API", kind="select", store="extra", options=["3", "2"], default="3", section="Avançado"),
        ] + _PERMS,
    ),
    "mixpanel": Connector(
        "mixpanel", "api", "Mixpanel", None, "Mixpanel via Service Account.",
        "GET no endpoint do projeto",
        fields=[
            Field("project_id", "Project ID", store="extra", required=True),
            Field("region", "Região / API host", kind="select", store="extra", options=["us", "eu"], default="us", section="Avançado"),
            Field("username", "Service Account Username", store="col:username", section="Autenticação"),
            Field("service_account_secret", "Service Account Secret", kind="password", store="secret", secret=True, section="Autenticação"),
            Field("project_token", "Project Token (opcional)", kind="password", store="secret", secret=True, section="Autenticação"),
        ] + _PERMS,
    ),
    "blip": Connector(
        "blip", "api", "Blip", None, "Blip (msging) via Authorization Key.",
        "GET/POST em comando seguro (ping)",
        fields=[
            Field("contract_id", "Contract ID", store="extra", required=True),
            Field("bot_id", "Bot ID (opcional)", store="extra"),
            Field("base_url", "Base URL", store="extra", placeholder="https://{contract_id}.http.msging.net"),
            Field("authorization_key", "Authorization Key", kind="password", store="secret", secret=True, required=True, section="Autenticação"),
        ] + _PERMS,
    ),
}


def get(connection_type: str) -> Connector | None:
    return REGISTRY.get(connection_type)


def secret_field_names(connection_type: str) -> list[str]:
    """Secret keys stored in the generic secrets blob (store == 'secret') for a type."""
    c = REGISTRY.get(connection_type)
    return [f.name for f in (c.fields if c else []) if f.secret and f.store == "secret"]


def as_json() -> list[dict]:
    """Serializable registry for the frontend (GET /connections/types)."""
    out = []
    for c in REGISTRY.values():
        d = {"type": c.type, "category": c.category, "label": c.label,
             "default_port": c.default_port, "description": c.description, "test_hint": c.test_hint,
             "fields": [asdict(f) for f in c.fields]}
        out.append(d)
    return out
