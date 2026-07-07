from __future__ import annotations

import socket

from t2c_ingest.core.crypto import decrypt_secret
from t2c_ingest.models.connection import Connection

# Simple validation query for both engines.
_VALIDATION_QUERY = "SELECT 1"


def _resolve_ipv4(host: str, port: int) -> str | None:
    """Return an IPv4 address for ``host`` when available.

    Docker's default bridge network usually has no IPv6 route, so a host with an AAAA record
    (or an IPv6-preferring resolver) fails with 'Network is unreachable'. Preferring the A
    record (IPv4) makes the test work against dual-stack hosts. Returns None if the host has
    no IPv4 (e.g. an IPv6 literal) — the driver then uses the host as given.
    """
    try:
        infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
    except (socket.gaierror, OSError):
        return None
    for info in infos:
        addr = info[4][0]
        if addr:
            return addr
    return None


def test_connection(conn: Connection) -> tuple[bool, str]:
    """Open a real connection to the target database and run ``SELECT 1``.

    Returns (ok, message). Never raises — driver/network errors become a friendly message.
    """
    password = decrypt_secret(conn.password_encrypted)
    host = conn.host or "localhost"
    if conn.connection_type == "postgres":
        return _test_postgres(conn, host, password)
    if conn.connection_type == "mysql":
        return _test_mysql(conn, host, password)
    return False, f"Tipo de conexão não suportado: {conn.connection_type}"


def _test_postgres(conn: Connection, host: str, password: str) -> tuple[bool, str]:
    try:
        import psycopg
    except ImportError:  # pragma: no cover
        return False, "Driver psycopg indisponível no servidor."
    port = conn.port or 5432
    sslmode = "require" if conn.ssl_enabled else "prefer"
    # Prefer IPv4 (Docker bridge has no IPv6 route); keep host for auth/SSL via hostaddr.
    ipv4 = _resolve_ipv4(host, port)
    connect_kwargs = dict(
        host=host,
        port=port,
        dbname=conn.database_name or "postgres",
        user=conn.username or "",
        password=password,
        connect_timeout=8,
        sslmode=sslmode,
    )
    if ipv4:
        connect_kwargs["hostaddr"] = ipv4
    try:
        with psycopg.connect(**connect_kwargs) as db:
            with db.cursor() as cur:
                cur.execute(_VALIDATION_QUERY)
                cur.fetchone()
        return True, f"Conectado com sucesso a {host}:{port}."
    except Exception as exc:  # noqa: BLE001
        return False, _friendly_error(str(exc))


def _test_mysql(conn: Connection, host: str, password: str) -> tuple[bool, str]:
    try:
        import pymysql
    except ImportError:  # pragma: no cover
        return False, "Driver pymysql indisponível no servidor."
    port = conn.port or 3306
    ssl = {"ssl": {}} if conn.ssl_enabled else {}
    # Prefer IPv4 for the same reason as Postgres (pymysql has no hostaddr, so use the IPv4).
    connect_host = _resolve_ipv4(host, port) or host
    try:
        db = pymysql.connect(
            host=connect_host,
            port=port,
            database=conn.database_name or None,
            user=conn.username or "",
            password=password,
            connect_timeout=8,
            read_timeout=8,
            **ssl,
        )
        try:
            with db.cursor() as cur:
                cur.execute(_VALIDATION_QUERY)
                cur.fetchone()
        finally:
            db.close()
        return True, f"Conectado com sucesso a {host}:{port}."
    except Exception as exc:  # noqa: BLE001
        return False, _friendly_error(str(exc))


def _friendly_error(detail: str) -> str:
    low = detail.lower()
    if "authentication" in low or "access denied" in low or "password" in low:
        return "Falha de autenticação: usuário ou senha inválidos."
    if "could not translate host name" in low or "name or service not known" in low or "getaddrinfo" in low:
        return "Host não encontrado. Verifique o endereço do servidor."
    if "network is unreachable" in low or "no route to host" in low:
        return (
            "Rede inacessível até o host (possível tentativa via IPv6 sem rota no container). "
            "Verifique se o banco aceita IPv4 e se o host está acessível a partir do ambiente."
        )
    if "connection refused" in low or "can't connect" in low or "could not connect" in low:
        return "Conexão recusada. Verifique host/porta e se o banco está acessível."
    if "timeout" in low or "timed out" in low:
        return "Tempo limite excedido ao conectar."
    if "does not exist" in low or "unknown database" in low:
        return "Banco de dados não encontrado."
    return f"Falha ao conectar: {detail[:200]}"
