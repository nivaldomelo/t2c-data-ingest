"""Resolve registered connections for a job's Spark/Python execution.

A job references connections through its arguments as ``--<role>-connection <name|id>``
(e.g. ``--source-connection mysql_1 --target-connection postgres_1``). The worker resolves
each to a registered connection, validates it is active, decrypts the password, and exposes
the credentials to the job process as environment variables prefixed by the role:

    --source-connection  -> SOURCE_*   (SOURCE_HOST, SOURCE_PORT, SOURCE_DB, SOURCE_USER,
                                         SOURCE_PASSWORD, SOURCE_TYPE, SOURCE_SSL, SOURCE_SCHEMA)
    --target-connection  -> TARGET_*

Passwords travel ONLY via env vars, never via CLI args and never logged.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from t2c_ingest.core.crypto import decrypt_secret
from t2c_ingest.features.connections.repository import get_connection_by_ref
from t2c_ingest.features.connections.service import test_connection


@dataclass
class ResolvedConnections:
    env: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)   # safe, no secrets
    error: str | None = None
    spark_confs: list[str] = field(default_factory=list)   # non-secret --conf (e.g. s3a endpoint)
    secret_values: list[str] = field(default_factory=list)  # decrypted secrets to mask in logs


def _prefix_for_flag(flag: str) -> str:
    # "--source-connection" -> "SOURCE_"
    role = flag.lstrip("-")
    if role.endswith("-connection"):
        role = role[: -len("-connection")]
    return role.replace("-", "_").upper() + "_"


def _extract_refs(arguments: list) -> dict[str, str]:
    """Return {prefix: ref} for every ``--<role>-connection <value>`` pair in the args."""
    refs: dict[str, str] = {}
    args = [str(a) for a in (arguments or [])]
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--") and a.endswith("-connection") and i + 1 < len(args):
            refs[_prefix_for_flag(a)] = args[i + 1]
            i += 2
        elif a.startswith("--") and "-connection=" in a:
            flag, _, value = a.partition("=")
            refs[_prefix_for_flag(flag)] = value
            i += 1
        else:
            i += 1
    return refs


def resolve_connections(db: Session, arguments: list, *, test: bool = True) -> ResolvedConnections:
    """Resolve, validate and (optionally) test the connections referenced by the arguments.

    Returns a ResolvedConnections with the env dict to inject. On any problem, ``error`` is set
    with a friendly message and the caller should fail the execution before submitting.
    """
    result = ResolvedConnections()
    refs = _extract_refs(arguments)
    if not refs:
        return result  # no connections referenced — nothing to inject

    for prefix, ref in refs.items():
        conn = get_connection_by_ref(db, ref)
        if conn is None:
            result.error = f"Conexão '{ref}' não encontrada (referenciada por {prefix[:-1].lower()})."
            return result
        if not conn.active:
            result.error = f"Conexão '{conn.name}' está inativa e não pode ser usada."
            return result

        if conn.connection_type == "s3":
            _inject_s3(result, prefix, conn, test=test)
            if result.error:
                return result
            continue

        password = decrypt_secret(conn.password_encrypted)
        result.env.update(
            {
                f"{prefix}TYPE": conn.connection_type or "",
                f"{prefix}HOST": conn.host or "",
                f"{prefix}PORT": str(conn.port or ""),
                f"{prefix}DB": conn.database_name or "",
                f"{prefix}USER": conn.username or "",
                f"{prefix}PASSWORD": password,
                f"{prefix}SSL": "true" if conn.ssl_enabled else "false",
                f"{prefix}SCHEMA": conn.schema_name or "",
            }
        )
        # Safe note (no secrets).
        result.notes.append(
            f"{prefix[:-1].lower()}-connection '{conn.name}' -> {conn.connection_type} "
            f"{conn.host}:{conn.port}/{conn.database_name} (ativa)"
        )

        if test:
            ok, message = test_connection(conn)
            result.notes.append(f"  teste {conn.name}: {'OK' if ok else 'FALHOU'} - {message}")
            if not ok:
                result.error = f"Teste de conectividade falhou para '{conn.name}': {message}"
                return result

    return result


def _inject_s3(result: "ResolvedConnections", prefix: str, conn, *, test: bool) -> None:
    """Inject S3 config for a job: role-prefixed non-secret env, standard AWS_* creds (via env,
    for boto3 AND the S3A default provider chain — never on the command line), and non-secret
    spark s3a --conf. Secrets are tracked for log masking."""
    from t2c_ingest.features.connections import s3_service

    cfg = s3_service.s3_settings(conn)
    creds = s3_service.resolve_aws_credentials(conn)  # {} for instance_profile/environment
    result.env.update({
        f"{prefix}TYPE": "s3",
        f"{prefix}S3_BUCKET": cfg.bucket or "",
        f"{prefix}S3_PREFIX": cfg.base_prefix or "",
        f"{prefix}S3_REGION": cfg.region or "",
        f"{prefix}S3_ENDPOINT": cfg.endpoint_url or "",
        f"{prefix}S3_LAYER": cfg.default_layer or "",
    })
    # Standard AWS env (only via env -> never on the Spark command line). The S3A default
    # credential chain and boto3 both read these.
    ak = creds.get("aws_access_key_id")
    if ak:
        result.env["AWS_ACCESS_KEY_ID"] = ak
        result.env["AWS_SECRET_ACCESS_KEY"] = creds.get("aws_secret_access_key", "")
        result.secret_values += [ak, creds.get("aws_secret_access_key", "")]
        if creds.get("aws_session_token"):
            result.env["AWS_SESSION_TOKEN"] = creds["aws_session_token"]
            result.secret_values.append(creds["aws_session_token"])
    if cfg.region:
        result.env.setdefault("AWS_REGION", cfg.region)
        result.env.setdefault("AWS_DEFAULT_REGION", cfg.region)
    if cfg.endpoint_url:
        result.env.setdefault("AWS_ENDPOINT_URL_S3", cfg.endpoint_url)
        # Non-secret spark s3a confs (endpoint/region/path-style/ssl). Credentials come from env.
        result.spark_confs += [
            f"spark.hadoop.fs.s3a.endpoint={cfg.endpoint_url}",
            "spark.hadoop.fs.s3a.path.style.access=true",
            f"spark.hadoop.fs.s3a.connection.ssl.enabled={'true' if cfg.ssl_enabled else 'false'}",
        ]
    if cfg.region:
        result.spark_confs.append(f"spark.hadoop.fs.s3a.endpoint.region={cfg.region}")
    result.notes.append(
        f"{prefix[:-1].lower()}-connection '{conn.name}' -> s3 {cfg.bucket}/{cfg.base_prefix} "
        f"(auth={cfg.auth_mode}, ativa)"
    )
    if test:
        r = s3_service.test_connection(conn, attempt_write=False)
        result.notes.append(f"  teste {conn.name}: {'OK' if r['success'] else 'FALHOU'} - {r['message']}")
        if not r["success"]:
            result.error = f"Teste S3 falhou para '{conn.name}': {r['message']}"
