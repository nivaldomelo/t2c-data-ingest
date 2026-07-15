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


def _inject_db_conn(result: ResolvedConnections, prefix: str, conn) -> None:
    """Injeta credenciais de uma conexão de banco sob um prefixo (SOURCE_/TARGET_), só via env."""
    password = decrypt_secret(conn.password_encrypted)
    result.env.update({
        f"{prefix}TYPE": conn.connection_type or "",
        f"{prefix}HOST": conn.host or "",
        f"{prefix}PORT": str(conn.port or ""),
        f"{prefix}DB": conn.database_name or "",
        f"{prefix}USER": conn.username or "",
        f"{prefix}PASSWORD": password,
        f"{prefix}SSL": "true" if conn.ssl_enabled else "false",
        f"{prefix}SCHEMA": conn.schema_name or "",
    })
    if password:
        result.secret_values.append(password)


def _find_control(db: Session, job):
    """Localiza o registro de controle: job.ingestion_control_id ou arg --control-id."""
    from t2c_ingest.features.ingestion_control.models import IngestionControl
    cid = getattr(job, "ingestion_control_id", None)
    if not cid:
        args = [str(a) for a in (job.arguments or [])]
        for i, a in enumerate(args):
            if a == "--control-id" and i + 1 < len(args):
                cid = args[i + 1]
                break
            if a.startswith("--control-id="):
                cid = a.split("=", 1)[1]
                break
    if not cid:
        return None
    try:
        return db.get(IngestionControl, int(cid))
    except (ValueError, TypeError):
        return None


def resolve_control(db: Session, job, result: ResolvedConnections) -> dict | None:
    """CTRL-1: resolve origem+destino declarativamente a partir do Controle de Ingestão e injeta
    SOURCE_*/TARGET_* (credenciais só via env). Retorna resumo p/ registrar na execução."""
    from t2c_ingest.features.ingestion_control import resolvers
    from t2c_ingest.models.connection import Connection

    control = _find_control(db, job)
    if control is None:
        return None

    src = resolvers.resolve_source(db, control)
    tgt = resolvers.resolve_target(db, control)

    if not control.source_connection_id and not (tgt.get("connection_id") or tgt.get("destination_id")):
        result.notes.append(
            "[WARN] Controle de ingestão não possui origem/destino declarativos completos. "
            "Usando argumentos legados do job."
        )
        return None

    # Credenciais + config de origem (SOURCE_*).
    if control.source_connection_id:
        sconn = db.get(Connection, control.source_connection_id)
        if sconn:
            _inject_s3(result, "SOURCE_", sconn, test=False) if sconn.connection_type == "s3" \
                else _inject_db_conn(result, "SOURCE_", sconn)
    result.env.update(resolvers.source_env(src))

    # Credenciais + config de destino (TARGET_*).
    tconn_id = tgt.get("connection_id")
    if tconn_id:
        tconn = db.get(Connection, tconn_id)
        if tconn:
            _inject_s3(result, "TARGET_", tconn, test=False) if tconn.connection_type == "s3" \
                else _inject_db_conn(result, "TARGET_", tconn)
    result.env.update(resolvers.target_env(tgt))

    result.notes.append(
        f"controle #{control.id} '{control.nome_tabela}': origem {src.get('source_type')} "
        f"-> destino {tgt.get('target_type')} (write_mode={tgt.get('write_mode')})"
    )
    return {
        "control_id": control.id,
        "source_connection_id": control.source_connection_id,
        "target_connection_id": tgt.get("connection_id"),
        "destination_id": tgt.get("destination_id"),
        "source_summary": src,
        "target_summary": tgt,
    }


def resolve_destination(db: Session, job, result: ResolvedConnections) -> dict | None:
    """Resolve o destino declarativo do job (DEST-1) e injeta a config de escrita + credenciais
    da conexão sob o prefixo TARGET_. Retorna um resumo p/ registrar na execução, ou None.

    Compatível: se o job não tem destination_id, apenas emite um aviso quando há args legados de
    destino, e retorna None (o job usa os argumentos antigos)."""
    from t2c_ingest.models.connection import Connection
    from t2c_ingest.models.destination import Destination
    from t2c_ingest.features.destinations import resolver as dest_resolver

    dest_id = getattr(job, "destination_id", None)
    if not dest_id:
        refs = _extract_refs(job.arguments or [])
        if any(p.startswith("TARGET") for p in refs):
            result.notes.append("Destino configurável não informado. Usando argumentos legados de destino.")
        return None

    dest = db.get(Destination, dest_id)
    if not dest or dest.deleted_at is not None:
        result.error = f"Destino (id={dest_id}) não encontrado ou removido."
        return None
    conn = db.get(Connection, dest.connection_id)
    if not conn:
        result.error = f"Conexão do destino '{dest.name}' não encontrada."
        return None
    if not conn.active:
        result.error = f"Conexão '{conn.name}' do destino '{dest.name}' está inativa."
        return None

    # Credenciais da conexão sob o prefixo TARGET_ (nunca na linha de comando).
    if conn.connection_type == "s3":
        _inject_s3(result, "TARGET_", conn, test=False)
    else:
        _inject_db_conn(result, "TARGET_", conn)

    # Destino template: descobre a tabela em runtime (arg do job ou Controle de Ingestão).
    runtime_table = _runtime_table(db, job) if dest.is_template else None
    if dest.is_template and not runtime_table:
        result.notes.append(
            f"Destino '{dest.name}' é template mas nenhuma tabela foi informada em runtime "
            "(arg --table / --table-name ou Controle de Ingestão). O job deve fornecê-la."
        )

    # Config declarativa do destino (não-secreta) + nome da conexão.
    result.env.update(dest_resolver.target_env(dest, runtime_table))
    result.env["TARGET_CONNECTION_NAME"] = conn.name
    result.notes.append(
        f"destino '{dest.name}' -> {dest.destination_type} "
        f"({dest_resolver.target_display(dest, runtime_table)}, write_mode={dest.write_mode})"
    )
    return {
        "destination_id": dest.id,
        "destination_type": dest.destination_type,
        "summary": dest_resolver.normalized(dest, conn, runtime_table),
    }


def _runtime_table(db: Session, job) -> str | None:
    """Nome da tabela em runtime para um destino template: 1) arg do job (--table/--table-name/
    --target-table/--nome-tabela); 2) Controle de Ingestão vinculado (nome_tabela)."""
    args = [str(a) for a in (job.arguments or [])]
    flags = {"--table", "--table-name", "--target-table", "--nome-tabela"}
    i = 0
    while i < len(args):
        a = args[i]
        if a in flags and i + 1 < len(args):
            return args[i + 1]
        if a.startswith("--") and "=" in a and a.split("=", 1)[0] in flags:
            return a.split("=", 1)[1]
        i += 1
    ic_id = getattr(job, "ingestion_control_id", None)
    if ic_id:
        try:
            from t2c_ingest.features.ingestion_control.models import IngestionControl
            ic = db.get(IngestionControl, ic_id)
            if ic and ic.nome_tabela:
                # nome_tabela pode vir "schema.tabela" — usa só o último segmento para o alvo.
                return ic.nome_tabela.split(".")[-1]
        except Exception:  # noqa: BLE001
            return None
    return None


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


# ─────────────────────── Carga multi-destino (job genérico controlado) ───────────────────────

def _control_selector(job) -> tuple[str, str] | None:
    """Extrai (kind, value) de --control-id/--control-name/--control-group dos args do job."""
    args = [str(a) for a in (job.arguments or [])]
    for kind in ("control-id", "control-name", "control-group"):
        flag = f"--{kind}"
        for i, a in enumerate(args):
            if a == flag and i + 1 < len(args):
                return kind, args[i + 1]
            if a.startswith(flag + "="):
                return kind, a.split("=", 1)[1]
    return None


def _match_controls(db: Session, kind: str, value: str) -> list:
    from t2c_ingest.features.ingestion_control.models import IngestionControl
    from sqlalchemy import select

    if kind == "control-id":
        try:
            row = db.get(IngestionControl, int(value))
        except (ValueError, TypeError):
            return []
        return [row] if row else []
    if kind == "control-name":
        return list(db.scalars(select(IngestionControl).where(IngestionControl.nome_tabela == value)))
    if kind == "control-group":
        return list(db.scalars(
            select(IngestionControl).where(IngestionControl.grupo == value)
            .order_by(IngestionControl.id)))
    return []


def build_controlled_config(db: Session, job, result: ResolvedConnections) -> dict | None:
    """Carga multi-destino declarativa: monta um JSON (T2C_CONTROL_CONFIG) descrevendo origem +
    N destinos de cada controle selecionado, e injeta as CREDENCIAIS por conexão via env
    (T2C_CONN_{id}_PASSWORD para bancos; AWS_* + s3a --conf para S3). O job genérico lê o JSON e
    grava em cada destino na ordem. Retorna {control_ids, primary_control_id} ou None (não é uma
    carga controlada multi-destino)."""
    import json

    from t2c_ingest.features.ingestion_control import destinations_service as icd
    from t2c_ingest.features.ingestion_control import resolvers
    from t2c_ingest.models.connection import Connection

    sel = _control_selector(job)
    if not sel:
        return None
    controls = _match_controls(db, *sel)
    controls = [c for c in controls if icd.resolve_control_destinations(db, c.id)]
    if not controls:
        return None

    injected_conn: set[int] = set()

    def _inject_conn(conn: Connection) -> None:
        if not conn or conn.id in injected_conn:
            return
        injected_conn.add(conn.id)
        if conn.connection_type == "s3":
            _inject_s3(result, f"DL{conn.id}_", conn, test=False)  # AWS_* + s3a --conf (global)
        else:
            pw = decrypt_secret(conn.password_encrypted) if conn.password_encrypted else ""
            result.env[f"T2C_CONN_{conn.id}_PASSWORD"] = pw
            if pw:
                result.secret_values.append(pw)

    cfg_controls = []
    for control in controls:
        src = resolvers.resolve_source(db, control)
        sconn = db.get(Connection, control.source_connection_id) if control.source_connection_id else None
        if not sconn:
            result.notes.append(f"[WARN] controle #{control.id} sem conexão de origem; ignorado.")
            continue
        _inject_conn(sconn)
        dests = []
        for link in icd.resolve_control_destinations(db, control.id):
            d = link["destination"]
            dconn = db.get(Connection, d.connection_id)
            _inject_conn(dconn)
            entry = {
                "role": link["role"], "write_order": link["write_order"],
                "required": link["required"], "stop_on_failure": link["stop_on_failure"],
                "destination_id": d.id, "type": d.destination_type, "conn_id": d.connection_id,
                "write_mode": d.write_mode, "file_format": d.file_format,
                "compression": d.compression, "partition_columns": d.partition_columns or [],
                "target_schema": d.target_schema, "target_table": d.target_table or (src.get("table")),
                "staging_schema": d.staging_schema or d.target_schema,
                "staging_table": d.staging_table, "primary_key_columns": d.primary_key_columns or [],
                "target_bucket": d.target_bucket, "target_path": d.target_path,
                "target_layer": d.target_layer,
                "conn": _conn_public(dconn),
            }
            dests.append(entry)
        cfg_controls.append({
            "control_id": control.id, "nome_tabela": control.nome_tabela,
            "tipo_ingestao": control.tipo_ingestao, "colunas_chave": control.colunas_chave,
            "source": {**{k: src.get(k) for k in ("source_type", "database", "schema", "table",
                                                   "incremental_column", "watermark")},
                       "conn_id": sconn.id, "conn": _conn_public(sconn)},
            "destinations": dests,
        })

    if not cfg_controls:
        return None
    # URL libpq da base do ingest (mesmo Postgres) p/ o job escrever watermark/status no Controle.
    from t2c_ingest.core.config import settings as _settings
    ingest_url = (_settings.database_url or "").replace("postgresql+psycopg://", "postgresql://")
    if ingest_url:
        result.env["T2C_INGEST_DB_URL"] = ingest_url
        import re as _re
        m = _re.search(r"://[^:]+:([^@]+)@", ingest_url)
        if m:
            result.secret_values.append(m.group(1))
    result.env["T2C_CONTROL_CONFIG"] = json.dumps({"controls": cfg_controls}, default=str)
    ids = [c["control_id"] for c in cfg_controls]
    result.notes.append(
        f"carga multi-destino: {len(ids)} controle(s) [{', '.join(map(str, ids))}], "
        f"destinos por papel resolvidos do banco (sem args hardcoded).")
    return {"control_ids": ids, "primary_control_id": ids[0] if len(ids) == 1 else None}


def _conn_public(conn) -> dict:
    """Config NÃO-secreta de uma conexão (a senha vai só via env T2C_CONN_{id}_PASSWORD)."""
    if not conn:
        return {}
    return {"id": conn.id, "name": conn.name, "type": conn.connection_type,
            "host": conn.host, "port": conn.port, "database": conn.database_name,
            "user": conn.username, "ssl": bool(conn.ssl_enabled)}
