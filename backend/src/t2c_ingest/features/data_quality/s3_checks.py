"""Data Quality para destinos S3 / Data Lake (ponto 15).

Valida, de forma leve (boto3 list + pyarrow footer — SEM Spark, SEM count() completo), que a
carga realmente materializou dados no S3: partição criada, arquivos gerados e não-vazios, Parquet
legível, colunas obrigatórias presentes, registros > 0 e batendo com o lido, e watermark avançou.
Nunca levanta exceção — falhas viram check 'skip'.
"""
from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy.orm import Session

from t2c_ingest.features.connections import s3_service
from t2c_ingest.models.connection import Connection
from t2c_ingest.models.destination import Destination
from t2c_ingest.models.execution import Execution

PARQUET_EXT = (".parquet", ".parq")


def _chk(name, status, *, severity="warning", category="s3", detail="", metrics=None) -> dict:
    return {"name": name, "status": status, "severity": severity, "category": category,
            "detail": detail, "metrics": metrics or {}}


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _s3_connection(db: Session, execution: Execution) -> Connection | None:
    if execution.target_connection_id:
        c = db.get(Connection, execution.target_connection_id)
        if c and c.connection_type == "s3":
            return c
    if execution.destination_id:
        d = db.get(Destination, execution.destination_id)
        if d:
            c = db.get(Connection, d.connection_id)
            if c and c.connection_type == "s3":
                return c
    return None


def _control(db: Session, execution: Execution):
    if not execution.control_id:
        return None
    try:
        from t2c_ingest.features.ingestion_control.models import IngestionControl
        return db.get(IngestionControl, execution.control_id)
    except Exception:  # noqa: BLE001
        return None


def is_s3_target(db: Session, execution: Execution, summary: dict) -> bool:
    if (summary.get("target_type") or "").lower() == "s3":
        return True
    if (execution.destination_type or "").lower() == "s3":
        return True
    return _s3_connection(db, execution) is not None


def evaluate(db: Session, execution: Execution, summary: dict) -> list[dict]:
    """Roda os checks de Data Lake para uma execução com destino S3."""
    conn = _s3_connection(db, execution)
    tsum = (execution.target_summary or {}).get("target", {}) if execution.target_summary else {}
    path = summary.get("target_path") or tsum.get("path")
    if not conn or not path:
        return [_chk("S3_TARGET_RESOLVED", "skip", detail="conexão/path S3 não resolvidos", category="s3")]

    parsed = urlparse(path)  # s3a://bucket/key/...
    bucket = parsed.netloc
    keybase = parsed.path.strip("/")
    partition_path = (summary.get("partition_path") or "").strip("/")
    prefix = f"{keybase}/{partition_path}/".replace("//", "/") if partition_path else f"{keybase}/"
    prefix = prefix.lstrip("/")

    tipo = (summary.get("tipo") or "").upper()
    control = _control(db, execution)
    extra = (control.extra_params or {}) if control else {}
    crit = (control.criticality if control else "") or ""
    checks: list[dict] = []

    # ── Listagem (boto3) ──
    files, total_size, newest_key = [], 0, None
    try:
        client = s3_service.build_client(conn)
        token = None
        while True:
            kw = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
            if token:
                kw["ContinuationToken"] = token
            resp = client.list_objects_v2(**kw)
            for o in resp.get("Contents", []):
                base = o["Key"].rsplit("/", 1)[-1]
                if base.startswith("_") or base.startswith("."):
                    continue  # ignora _SUCCESS e afins
                if not o["Key"].lower().endswith(PARQUET_EXT):
                    continue
                files.append(o)
                total_size += int(o.get("Size", 0) or 0)
                if newest_key is None or (o.get("LastModified") and o["LastModified"] >= max(
                        (x.get("LastModified") for x in files), default=o["LastModified"])):
                    newest_key = o["Key"]
            if not resp.get("IsTruncated") or len(files) >= 5000:
                break
            token = resp.get("NextContinuationToken")
    except Exception as exc:  # noqa: BLE001
        code = (exc.response.get("Error", {}).get("Code") if hasattr(exc, "response") else None) or type(exc).__name__
        return [_chk("S3_PARTITION_CREATED", "skip", detail=f"não foi possível listar o S3: {code}",
                     category="partition")]

    files_count = len(files)
    # 1) Partição criada
    checks.append(_chk(
        "S3_PARTITION_CREATED", "pass" if files_count > 0 else "fail",
        severity="critical", category="partition",
        detail=(f"{files_count} arquivo(s) em {partition_path or '(raiz)'}" if files_count else "nenhum objeto na partição esperada"),
        metrics={"partition_path": partition_path or None, "files_found": files_count},
    ))
    # 2) Arquivos gerados
    checks.append(_chk(
        "S3_FILES_CREATED", "pass" if files_count > 0 else "fail", severity="critical", category="files",
        detail=f"files_count={files_count}", metrics={"files_count": files_count, "total_size_bytes": total_size},
    ))
    # 3) Arquivos não-vazios
    checks.append(_chk(
        "S3_FILES_NON_EMPTY", "pass" if total_size > 0 else ("fail" if files_count else "skip"),
        severity="warning", category="files", detail=f"total_size_bytes={total_size}",
        metrics={"total_size_bytes": total_size},
    ))

    # 4/5/6) Parquet legível + schema/colunas obrigatórias
    schema_cols: list[str] = []
    if newest_key:
        try:
            import pyarrow.parquet as pq
            from t2c_ingest.features.data_lake import scan_engine
            fs = scan_engine._pa_filesystem(conn)
            with fs.open_input_file(f"{bucket}/{newest_key}") as f:
                schema = pq.read_schema(f)
            schema_cols = [fld.name for fld in schema]
            checks.append(_chk("S3_PARQUET_READABLE", "pass", severity="critical", category="schema",
                               detail=f"{len(schema_cols)} coluna(s)", metrics={"columns": len(schema_cols)}))
        except Exception as exc:  # noqa: BLE001
            checks.append(_chk("S3_PARQUET_READABLE", "fail", severity="critical", category="schema",
                               detail=f"falha ao ler Parquet: {type(exc).__name__}"))
    else:
        checks.append(_chk("S3_PARQUET_READABLE", "skip", category="schema", detail="sem arquivo p/ validar"))

    required = extra.get("required_columns") or []
    if required:
        if schema_cols:
            missing = [c for c in required if c not in schema_cols]
            checks.append(_chk(
                "S3_REQUIRED_COLUMNS_PRESENT", "pass" if not missing else "fail",
                severity="critical", category="schema",
                detail=("todas presentes" if not missing else f"faltando: {', '.join(missing)}"),
                metrics={"missing_columns": missing},
            ))
            # Schema compatível (v1 = colunas obrigatórias presentes)
            checks.append(_chk("S3_SCHEMA_COMPATIBLE", "pass" if not missing else "fail",
                               severity="warning", category="schema",
                               detail="colunas obrigatórias presentes" if not missing else "colunas obrigatórias ausentes"))
        else:
            checks.append(_chk("S3_REQUIRED_COLUMNS_PRESENT", "skip", category="schema", detail="schema não lido"))

    # 7) Registros gravados > 0
    gravados = _to_int(summary.get("gravados"))
    if gravados is not None:
        if gravados > 0:
            checks.append(_chk("S3_RECORDS_WRITTEN_GT_ZERO", "pass", category="volume",
                               detail=f"gravados={gravados}", metrics={"records_written": gravados}))
        else:
            # incremental sem dados = informativo; full ou crítica = falha
            st = "info" if (tipo == "INCREMENTAL" and crit not in ("alta", "critica")) else "fail"
            checks.append(_chk("S3_RECORDS_WRITTEN_GT_ZERO", st,
                               severity="critical" if st == "fail" else "info", category="volume",
                               detail="carga gravou zero registros"))
    # 8) Gravados x lidos (com tolerância)
    lidos = _to_int(summary.get("lidos"))
    if lidos is not None and gravados is not None:
        tol = float(extra.get("records_tolerance_percent") or 0)
        diff_pct = (abs(gravados - lidos) / lidos * 100) if lidos else (0 if gravados == 0 else 100)
        ok = gravados == lidos or diff_pct <= tol
        checks.append(_chk("S3_RECORDS_WRITTEN_MATCH_EXPECTED", "pass" if ok else "warn",
                           category="volume", detail=f"lidos={lidos} gravados={gravados} (tol={tol}%)",
                           metrics={"records_read": lidos, "records_written": gravados, "diff_percent": round(diff_pct, 2)}))
    # 9) Watermark avançou (incremental)
    if tipo == "INCREMENTAL":
        wb, wa = summary.get("watermark_anterior"), summary.get("watermark_novo")
        advanced = bool(wa and (not wb or str(wa) > str(wb)))
        if advanced:
            checks.append(_chk("S3_WATERMARK_ADVANCED", "pass", category="watermark",
                               detail=f"{wb} -> {wa}"))
        else:
            st = "info" if crit not in ("alta", "critica") else "warn"
            checks.append(_chk("S3_WATERMARK_ADVANCED", st, severity="info" if st == "info" else "warning",
                               category="watermark", detail="watermark não avançou (sem novos registros?)"))
    return checks
