"""Per-type connection tests for the new connectors (databases via SQLAlchemy/pymongo, APIs via
httpx). Every function returns (ok, message) and NEVER raises — driver/network/credential errors
become a friendly message. Secrets are read from the encrypted blob and never logged.
"""
from __future__ import annotations

import time

from t2c_ingest.core.crypto import decrypt_secret, decrypt_secrets
from t2c_ingest.features.connections.service import _friendly_error, _resolve_ipv4
from t2c_ingest.models.connection import Connection


def _ep(conn: Connection) -> dict:
    return conn.extra_params or {}


# ─────────────────────────────── Databases ───────────────────────────────

def test_sqlserver(conn: Connection) -> tuple[bool, str]:
    ep = _ep(conn)
    host, port = conn.host or "localhost", conn.port or 1433
    pwd = decrypt_secret(conn.password_encrypted)
    try:
        import pyodbc  # noqa: F401
    except ImportError:
        try:
            import pymssql  # noqa: F401
        except ImportError:
            return False, "Driver SQL Server indisponível no servidor (instale pyodbc ou pymssql)."
    try:
        from sqlalchemy import create_engine, text
        driver = (ep.get("driver") or "ODBC Driver 18 for SQL Server").replace(" ", "+")
        enc = "yes" if ep.get("encrypt", True) else "no"
        trust = "yes" if ep.get("trust_server_certificate") else "no"
        url = (f"mssql+pyodbc://{conn.username}:{pwd}@{host}:{port}/{conn.database_name or ''}"
               f"?driver={driver}&Encrypt={enc}&TrustServerCertificate={trust}")
        eng = create_engine(url, connect_args={"timeout": 8})
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        return True, f"Conectado com sucesso a {host}:{port}."
    except Exception as exc:  # noqa: BLE001
        return False, _friendly_error(str(exc))


def test_oracle(conn: Connection) -> tuple[bool, str]:
    ep = _ep(conn)
    host, port = conn.host or "localhost", conn.port or 1521
    pwd = decrypt_secret(conn.password_encrypted)
    try:
        import oracledb  # noqa: F401
    except ImportError:
        return False, "Driver Oracle indisponível no servidor (instale oracledb)."
    try:
        from sqlalchemy import create_engine, text
        svc, sid = ep.get("service_name"), ep.get("sid")
        if svc:
            dsn = f"{host}:{port}/{svc}"
        elif sid:
            dsn = f"{host}:{port}/{sid}"
        else:
            return False, "Informe service name ou SID para Oracle."
        eng = create_engine(f"oracle+oracledb://{conn.username}:{pwd}@{dsn}")
        with eng.connect() as c:
            c.execute(text("SELECT 1 FROM DUAL"))
        return True, f"Conectado com sucesso a {host}:{port}."
    except Exception as exc:  # noqa: BLE001
        return False, _friendly_error(str(exc))


def test_mariadb(conn: Connection) -> tuple[bool, str]:
    # MariaDB fala o protocolo MySQL — reusa o teste do pymysql.
    from t2c_ingest.features.connections.service import _test_mysql
    return _test_mysql(conn, conn.host or "localhost", decrypt_secret(conn.password_encrypted))


def test_mongodb(conn: Connection) -> tuple[bool, str]:
    ep = _ep(conn)
    secrets = decrypt_secrets(conn.secrets_encrypted)
    try:
        from pymongo import MongoClient
    except ImportError:
        return False, "Driver pymongo indisponível no servidor."
    conn_str = secrets.get("connection_string")
    try:
        if conn_str:
            client = MongoClient(conn_str, serverSelectionTimeoutMS=8000)
        else:
            host = _resolve_ipv4(conn.host or "localhost", conn.port or 27017) or conn.host or "localhost"
            client = MongoClient(
                host=host, port=conn.port or 27017,
                username=conn.username or None, password=decrypt_secret(conn.password_encrypted) or None,
                authSource=ep.get("auth_source") or "admin", tls=bool(ep.get("tls")),
                serverSelectionTimeoutMS=8000,
            )
        names = client.list_database_names()
        client.close()
        return True, f"Conectado com sucesso ({len(names)} database(s) visíveis)."
    except Exception as exc:  # noqa: BLE001
        return False, _friendly_error(str(exc))


# ─────────────────────────────── APIs (httpx) ───────────────────────────────

def _httpx():
    try:
        import httpx
        return httpx
    except ImportError:
        return None


def _rest_auth(conn: Connection) -> tuple[dict, dict, tuple | None]:
    """Return (headers, query_params, basic_auth) from the REST auth config + secrets."""
    ep = _ep(conn)
    secrets = decrypt_secrets(conn.secrets_encrypted)
    headers: dict = {}
    params: dict = {}
    basic: tuple | None = None
    auth = ep.get("auth_type") or "none"
    if auth == "api_key_header":
        headers[ep.get("api_key_name") or "x-api-key"] = secrets.get("api_key", "")
    elif auth == "api_key_query":
        params[ep.get("api_key_name") or "api_key"] = secrets.get("api_key", "")
    elif auth == "bearer_token":
        headers["Authorization"] = f"Bearer {secrets.get('access_token', '')}"
    elif auth == "basic_auth":
        basic = (conn.username or "", decrypt_secret(conn.password_encrypted))
    elif auth == "custom_header":
        headers[ep.get("custom_header_name") or "Authorization"] = secrets.get("custom_header_value", "")
    return headers, params, basic


def _http_get(url: str, *, headers=None, params=None, auth=None, timeout=15) -> tuple[bool, str]:
    httpx = _httpx()
    if httpx is None:
        return False, "Biblioteca httpx indisponível no servidor."
    try:
        t0 = time.monotonic()
        resp = httpx.get(url, headers=headers or {}, params=params or {}, auth=auth, timeout=timeout,
                         follow_redirects=True)
        ms = int((time.monotonic() - t0) * 1000)
        if 200 <= resp.status_code < 300:
            return True, f"HTTP {resp.status_code} em {ms}ms."
        if resp.status_code in (401, 403):
            return False, f"Autenticação/permissão negada (HTTP {resp.status_code})."
        return False, f"HTTP {resp.status_code} em {ms}ms — verifique a configuração."
    except Exception as exc:  # noqa: BLE001
        return False, _friendly_error(str(exc))


def test_rest_api(conn: Connection) -> tuple[bool, str]:
    ep = _ep(conn)
    base = (ep.get("base_url") or "").rstrip("/")
    if not base:
        return False, "Base URL não configurada."
    endpoint = (ep.get("test_endpoint") or "/").strip()
    url = base + ("/" + endpoint.lstrip("/") if endpoint else "")
    headers, params, basic = _rest_auth(conn)
    return _http_get(url, headers=headers, params=params, auth=basic, timeout=int(ep.get("timeout") or 30))


def test_jira(conn: Connection) -> tuple[bool, str]:
    ep = _ep(conn)
    base = (ep.get("base_url") or "").rstrip("/")
    if not base or not conn.username:
        return False, "Site URL e e-mail do usuário são obrigatórios."
    token = decrypt_secrets(conn.secrets_encrypted).get("api_token", "")
    ver = ep.get("api_version") or "3"
    ok, msg = _http_get(f"{base}/rest/api/{ver}/myself", headers={"Accept": "application/json"},
                        auth=(conn.username, token))
    return (True, f"Conectado ao Jira ({base}). {msg}") if ok else (False, msg)


def test_mixpanel(conn: Connection) -> tuple[bool, str]:
    ep = _ep(conn)
    if not ep.get("project_id"):
        return False, "Project ID é obrigatório."
    secrets = decrypt_secrets(conn.secrets_encrypted)
    host = "eu.mixpanel.com" if (ep.get("region") == "eu") else "mixpanel.com"
    # Basic auth com Service Account (username:secret). Endpoint leve de validação do projeto.
    ok, msg = _http_get(
        f"https://{host}/api/app/projects/{ep['project_id']}",
        auth=(conn.username or "", secrets.get("service_account_secret", "")),
    )
    return (True, f"Credenciais Mixpanel válidas (projeto {ep['project_id']}). {msg}") if ok else (False, msg)


def test_blip(conn: Connection) -> tuple[bool, str]:
    ep = _ep(conn)
    contract = ep.get("contract_id")
    base = (ep.get("base_url") or (f"https://{contract}.http.msging.net" if contract else "")).rstrip("/")
    if not base:
        return False, "Contract ID ou Base URL são obrigatórios."
    key = decrypt_secrets(conn.secrets_encrypted).get("authorization_key", "")
    httpx = _httpx()
    if httpx is None:
        return False, "Biblioteca httpx indisponível no servidor."
    # Comando seguro (ping): getResource não destrutivo.
    envelope = {"id": "t2c-conn-test", "method": "get", "uri": "/ping"}
    try:
        t0 = time.monotonic()
        resp = httpx.post(f"{base}/commands", json=envelope,
                          headers={"Authorization": f"Key {key}", "Content-Type": "application/json"},
                          timeout=15)
        ms = int((time.monotonic() - t0) * 1000)
        if resp.status_code in (200, 202):
            return True, f"Conectado ao Blip (contract {contract}) em {ms}ms."
        if resp.status_code in (401, 403):
            return False, "Authorization Key inválida ou sem permissão."
        return False, f"HTTP {resp.status_code} — verifique contract/base URL."
    except Exception as exc:  # noqa: BLE001
        return False, _friendly_error(str(exc))


DISPATCH = {
    "sqlserver": test_sqlserver,
    "oracle": test_oracle,
    "mariadb": test_mariadb,
    "mongodb": test_mongodb,
    "rest_api": test_rest_api,
    "jira": test_jira,
    "mixpanel": test_mixpanel,
    "blip": test_blip,
}
