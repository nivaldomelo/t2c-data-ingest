"""Monta o dicionário de variáveis do template a partir do Controle de Ingestão.

Reutiliza os resolvers da carga (origem + destinos por papel/override) e produz um dict achatado
de strings — SEM segredos (só metadados; credenciais ficam nas conexões, resolvidas no runtime).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from t2c_ingest.features.ingestion_control import destinations_service as icd
from t2c_ingest.features.ingestion_control import resolvers
from t2c_ingest.features.ingestion_control.models import IngestionControl


def _control_table(control, src: dict) -> str:
    tbl = src.get("table")
    if tbl:
        return tbl
    nome = (control.nome_tabela or "").strip()
    return nome.split(".")[-1] if nome else ""


def _s3_join(bucket, base_prefix, relative) -> str:
    if not bucket:
        return ""
    parts = [(base_prefix or "").strip("/"), (relative or "").strip("/")]
    tail = "/".join(p for p in parts if p)
    return f"s3a://{bucket}/{tail}/" if tail else f"s3a://{bucket}/"


def _pick(links: list[dict], role: str) -> dict | None:
    return next((l for l in links if l.get("role") == role), None)


def build_context(db: Session, template: dict, job_meta: dict, control_id: int | None) -> dict:
    """job_meta: {name, description, engine, job_type}. control_id opcional (recomendado)."""
    ctx: dict = {
        "job_name": job_meta.get("name") or "",
        "job_description": job_meta.get("description") or "",
        "engine": job_meta.get("engine") or template.get("engine") or "",
        "job_type": job_meta.get("job_type") or template.get("job_type") or "",
        "template_name": template.get("name") or template.get("id") or "",
        # defaults vazios (preenchidos se houver controle)
        "control_id": "", "control_name": "", "control_group": "",
        "source_name": "", "source_type": "", "source_database": "", "source_schema": "", "source_table": "",
        "primary_destination_name": "", "primary_destination_type": "", "primary_target_schema": "",
        "primary_target_table": "", "primary_write_mode": "", "primary_key_columns": "", "staging_table": "",
        "datalake_destination_name": "", "datalake_bucket": "", "datalake_base_prefix": "",
        "datalake_relative_path": "", "datalake_target_path": "", "file_format": "", "compression": "",
        "partition_columns": "",
        "ingestion_type": "", "incremental_column": "", "watermark_column": "",
        "expected_frequency": "", "sla_minutes": "", "owner_name": "",
        "run_command": "# Execute pelo T2C Data Ingest — o worker resolve o Controle e injeta a configuração.",
    }
    if not control_id:
        return ctx

    control = db.get(IngestionControl, control_id)
    if not control:
        return ctx

    src = resolvers.resolve_source(db, control)
    table = _control_table(control, src)
    links = icd.resolve_control_destinations(db, control.id)
    primary = _pick(links, "primary")
    datalake = _pick(links, "datalake_copy")

    ctx.update({
        "control_id": control.id,
        "control_name": control.nome_tabela or "",
        "control_group": control.grupo or "",
        "source_name": src.get("connection_name") or "",
        "source_type": src.get("source_type") or "",
        "source_database": src.get("database") or "",
        "source_schema": src.get("schema") or "",
        "source_table": table,
        "ingestion_type": control.tipo_ingestao or "",
        "incremental_column": src.get("incremental_column") or "",
        "watermark_column": src.get("incremental_column") or "",
        "expected_frequency": control.expected_frequency or "",
        "sla_minutes": control.sla_minutes if control.sla_minutes is not None else "",
        "owner_name": control.owner_name or "",
        "run_command": f"# via T2C Data Ingest (worker) — carga controlada por: --control-name {control.nome_tabela}",
    })

    if primary:
        d = primary["destination"]
        ov = primary.get("overrides") or {}
        schema = ov.get("target_schema") or d.target_schema or ""
        p_table = ov.get("target_table") or d.target_table or table
        keys = ov.get("primary_key_columns") or d.primary_key_columns or \
            [c.strip() for c in (control.colunas_chave or "").split(",") if c.strip()]
        staging = ov.get("staging_table") or d.staging_table or (f"stg_{p_table}_ingest" if p_table else "")
        ctx.update({
            "primary_destination_name": d.name,
            "primary_destination_type": d.destination_type,
            "primary_target_schema": schema,
            "primary_target_table": p_table,
            "primary_write_mode": ov.get("write_mode") or d.write_mode or "",
            "primary_key_columns": list(keys),
            "staging_table": staging,
        })

    if datalake:
        d = datalake["destination"]
        ov = datalake.get("overrides") or {}
        rel = ov.get("target_relative_path") or ov.get("target_table") or table
        base_prefix = d.target_prefix or ""
        path = d.target_path if (d.target_path and not ov.get("target_relative_path")) else \
            _s3_join(d.target_bucket, base_prefix, rel)
        ctx.update({
            "datalake_destination_name": d.name,
            "datalake_bucket": d.target_bucket or "",
            "datalake_base_prefix": base_prefix,
            "datalake_relative_path": rel,
            "datalake_target_path": path,
            "file_format": ov.get("file_format") or d.file_format or "",
            "compression": ov.get("compression") or d.compression or "",
            "partition_columns": ov.get("partition_columns") or d.partition_columns or [],
        })
    return ctx
