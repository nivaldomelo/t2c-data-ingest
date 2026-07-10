"""S3 / Data Lake connection service.

Resolves credentials per auth_mode, builds a boto3 S3 client, and validates a connection
(list / read / write to a temp prefix). Secrets are decrypted only in-process and never logged.
No object deletion in this version except the connection's own temporary test object.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from t2c_ingest.core.crypto import decrypt_secret
from t2c_ingest.models.connection import Connection

# Prefixes must be plain keys — no traversal, no absolute, no scheme, no wildcard.
_SAFE_PREFIX = re.compile(r"^[A-Za-z0-9._/=+\-]*$")
_TEST_PREFIX = "_t2c_connection_tests"


@dataclass
class S3Settings:
    region: str | None
    bucket: str | None
    base_prefix: str
    default_layer: str | None
    auth_mode: str
    endpoint_url: str | None
    role_arn: str | None
    external_id: str | None
    ssl_enabled: bool


def s3_settings(conn: Connection) -> S3Settings:
    ep = conn.extra_params or {}
    return S3Settings(
        region=ep.get("aws_region"),
        bucket=ep.get("bucket_name"),
        base_prefix=(ep.get("base_prefix") or "").strip("/"),
        default_layer=ep.get("default_layer"),
        auth_mode=ep.get("auth_mode") or "access_key",
        endpoint_url=ep.get("endpoint_url") or None,
        role_arn=ep.get("role_arn"),
        external_id=ep.get("external_id"),
        ssl_enabled=bool(ep.get("ssl_enabled", True)),
    )


def sanitize_prefix(prefix: str | None) -> str:
    """Reject path traversal / absolute / scheme; return a safe, relative key prefix."""
    p = (prefix or "").strip()
    if p.startswith("/") or p.startswith("\\") or "://" in p or ".." in p.replace("\\", "/").split("/"):
        raise ValueError("Prefixo inválido (não são permitidos caminhos absolutos, '..' ou esquema).")
    if not _SAFE_PREFIX.match(p):
        raise ValueError("Prefixo contém caracteres não permitidos.")
    return p.lstrip("/")


def resolve_aws_credentials(conn: Connection) -> dict:
    """Return explicit AWS credentials for the connection, or {} to use the default chain
    (instance_profile / environment). For iam_role, base creds come from the default chain and
    the role is assumed at client-build time."""
    cfg = s3_settings(conn)
    if cfg.auth_mode == "access_key":
        creds = {}
        if conn.aws_access_key_id_encrypted:
            creds["aws_access_key_id"] = decrypt_secret(conn.aws_access_key_id_encrypted)
        if conn.aws_secret_access_key_encrypted:
            creds["aws_secret_access_key"] = decrypt_secret(conn.aws_secret_access_key_encrypted)
        if conn.aws_session_token_encrypted:
            creds["aws_session_token"] = decrypt_secret(conn.aws_session_token_encrypted)
        return creds
    return {}  # iam_role/instance_profile/environment -> boto3 default chain (+ assume_role)


def build_client(conn: Connection):
    """Build a boto3 S3 client for the connection. Raises RuntimeError if boto3 is missing."""
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("boto3 indisponível no servidor.") from exc

    cfg = s3_settings(conn)
    session_kwargs = resolve_aws_credentials(conn)
    if cfg.region:
        session_kwargs["region_name"] = cfg.region

    if cfg.auth_mode == "iam_role" and cfg.role_arn:
        sts = boto3.client("sts", **session_kwargs)
        params = {"RoleArn": cfg.role_arn, "RoleSessionName": "t2c-data-ingest"}
        if cfg.external_id:
            params["ExternalId"] = cfg.external_id
        assumed = sts.assume_role(**params)["Credentials"]
        session_kwargs = {
            "aws_access_key_id": assumed["AccessKeyId"],
            "aws_secret_access_key": assumed["SecretAccessKey"],
            "aws_session_token": assumed["SessionToken"],
        }
        if cfg.region:
            session_kwargs["region_name"] = cfg.region

    client_kwargs = dict(session_kwargs)
    if cfg.endpoint_url:
        client_kwargs["endpoint_url"] = cfg.endpoint_url
        client_kwargs["use_ssl"] = cfg.ssl_enabled
    return boto3.client("s3", **client_kwargs)


def list_objects(conn: Connection, prefix: str | None = None, limit: int = 50) -> dict:
    """List up to ``limit`` objects under a (sanitized) prefix within the connection's bucket."""
    cfg = s3_settings(conn)
    if not cfg.bucket:
        raise ValueError("Conexão S3 sem bucket configurado.")
    pfx = sanitize_prefix(prefix if prefix is not None else cfg.base_prefix)
    client = build_client(conn)
    resp = client.list_objects_v2(Bucket=cfg.bucket, Prefix=pfx, MaxKeys=max(1, min(limit, 1000)))
    items = [{
        "key": o["Key"], "size": o.get("Size"),
        "last_modified": o.get("LastModified"), "storage_class": o.get("StorageClass"),
    } for o in resp.get("Contents", [])]
    return {"bucket": cfg.bucket, "prefix": pfx, "items": items}


def test_connection(conn: Connection, *, attempt_write: bool | None = None) -> dict:
    """Validate the S3 connection: list, read (if any object) and — when write is allowed —
    write a temp object. Returns {success, message, details}. Never raises."""
    cfg = s3_settings(conn)
    details: dict = {"bucket": cfg.bucket, "region": cfg.region, "base_prefix": cfg.base_prefix,
                     "auth_mode": cfg.auth_mode, "can_list": False, "can_read": False, "can_write": False}
    if not cfg.bucket:
        return {"success": False, "message": "Conexão S3 sem bucket configurado.", "details": details}
    do_write = conn.can_write if attempt_write is None else attempt_write
    try:
        client = build_client(conn)
        base = sanitize_prefix(cfg.base_prefix)
        listing = client.list_objects_v2(Bucket=cfg.bucket, Prefix=base, MaxKeys=5)
        details["can_list"] = True
        first = next(iter(listing.get("Contents", [])), None)
        if first:
            client.head_object(Bucket=cfg.bucket, Key=first["Key"])
            details["can_read"] = True
        if do_write:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            key = "/".join(p for p in [base, _TEST_PREFIX, f"test_{ts}.txt"] if p)
            client.put_object(Bucket=cfg.bucket, Key=key, Body=b"t2c-data-ingest connection test")
            details["can_write"] = True
            details["test_object"] = key
            try:  # clean up only our own temp test object; tolerate deny (no delete required)
                client.delete_object(Bucket=cfg.bucket, Key=key)
                details["test_object_removed"] = True
            except Exception:  # noqa: BLE001
                details["test_object_removed"] = False
        return {"success": True, "message": "Conexão S3 validada com sucesso.", "details": details}
    except Exception as exc:  # noqa: BLE001
        error_code = (exc.response.get("Error", {}).get("Code") if hasattr(exc, "response") else None) or type(exc).__name__
        details["error_code"] = error_code
        return {"success": False, "message": f"Não foi possível acessar o bucket informado: {error_code}", "details": details}
