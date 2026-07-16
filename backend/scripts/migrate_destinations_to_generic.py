"""Migra destinos por-tabela para destinos GENÉRICOS reutilizáveis, movendo o detalhe por-carga
para os overrides do vínculo (ingestion_control_destinations). Idempotente.

    docker compose exec api python scripts/migrate_destinations_to_generic.py           # dry-run
    docker compose exec api python scripts/migrate_destinations_to_generic.py --apply    # efetiva

O que faz:
  1) Garante os destinos genéricos (por nome): PostgreSQL Massa Teste, PostgreSQL Spark,
     Data Lake Bronze/Silver/Gold — reaproveitando conexão/schema/bucket/prefixo dos atuais.
  2) Para cada vínculo carga↔destino que aponta para um destino por-tabela, repontа para o
     genérico correspondente e preenche os overrides (tabela / path relativo / partições /
     chaves / staging) a partir do destino antigo.
  3) Inativa (soft) os destinos específicos/legados; mantém apenas os genéricos ativos.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from datetime import datetime, timezone  # noqa: E402

from sqlalchemy import select  # noqa: E402

from t2c_ingest.core.db import SessionLocal  # noqa: E402
from t2c_ingest.models.destination import Destination  # noqa: E402
from t2c_ingest.models.ingestion_control_destination import IngestionControlDestination  # noqa: E402

APPLY = "--apply" in sys.argv


def _log(msg: str) -> None:
    print(("APLICA " if APPLY else "DRY-RUN ") + msg)


def _get_or_create(db, *, name: str, defaults: dict) -> Destination:
    """Destino genérico idempotente por nome (dentre os não deletados)."""
    existing = db.scalar(select(Destination).where(Destination.name == name, Destination.deleted_at.is_(None)))
    if existing:
        _log(f"genérico já existe: {name} (#{existing.id})")
        return existing
    dest = Destination(name=name, created_by="migrate_destinations_to_generic",
                       updated_by="migrate_destinations_to_generic", active=True, **defaults)
    if APPLY:
        db.add(dest)
        db.flush()
    _log(f"criar genérico: {name} -> {defaults}")
    return dest


def main() -> None:
    with SessionLocal() as db:
        dests = {d.id: d for d in db.scalars(select(Destination)).all()}

        # Inferir conexões/bucket a partir dos destinos por-tabela existentes (fallback aos exemplos §14).
        pg_sample = next((d for d in dests.values() if d.destination_type == "postgres" and d.target_schema == "massa_teste"), None)
        s3_sample = next((d for d in dests.values() if d.destination_type == "s3" and (d.target_layer == "bronze")), None)
        pg_conn = pg_sample.connection_id if pg_sample else None
        pg_db = pg_sample.target_database if pg_sample else None
        s3_conn = s3_sample.connection_id if s3_sample else None
        s3_bucket = s3_sample.target_bucket if s3_sample else "datalake-t2c-data-integracao"

        # 1) Destinos genéricos.
        generic: dict[str, Destination] = {}
        if pg_conn:
            generic["pg_massa_teste"] = _get_or_create(db, name="PostgreSQL Massa Teste", defaults=dict(
                destination_type="postgres", connection_id=pg_conn, target_database=pg_db,
                target_schema="massa_teste", staging_schema="massa_teste", write_mode="upsert"))
            generic["pg_spark"] = _get_or_create(db, name="PostgreSQL Spark", defaults=dict(
                destination_type="postgres", connection_id=pg_conn, target_database=pg_db,
                target_schema="spark", staging_schema="spark", write_mode="upsert"))
        if s3_conn:
            for layer in ("bronze", "silver", "gold"):
                generic[f"dl_{layer}"] = _get_or_create(db, name=f"Data Lake {layer.capitalize()}", defaults=dict(
                    destination_type="s3", connection_id=s3_conn, target_bucket=s3_bucket,
                    target_prefix=layer, target_layer=layer, file_format="parquet",
                    compression="snappy", write_mode="append"))

        # 2) Repontar vínculos por-tabela → genérico + overrides.
        links = db.scalars(select(IngestionControlDestination)).all()
        for l in links:
            d = dests.get(l.destination_id)
            if not d or d.is_template:
                continue
            if d.destination_type == "postgres" and d.target_table:
                gen = generic.get("pg_spark") if d.target_schema == "spark" else generic.get("pg_massa_teste")
                if not gen:
                    continue
                ov = dict(target_schema=d.target_schema, target_table=d.target_table,
                          staging_table=d.staging_table, primary_key_columns=d.primary_key_columns,
                          write_mode=d.write_mode)
                _log(f"vínculo #{l.id} (ctrl {l.control_id}): {d.name} -> {gen.name} + {ov}")
                if APPLY:
                    l.destination_id = gen.id
                    l.target_schema, l.target_table = d.target_schema, d.target_table
                    l.staging_table, l.primary_key_columns = d.staging_table, d.primary_key_columns
                    l.write_mode = d.write_mode
                    l.updated_at = datetime.now(timezone.utc)
            elif d.destination_type == "s3":
                gen = generic.get(f"dl_{d.target_layer}") or generic.get("dl_bronze")
                if not gen:
                    continue
                # prefixo por-tabela "bronze/clientes" → path relativo "clientes" sobre a base "bronze".
                base = (gen.target_prefix or "").strip("/")
                rel = (d.target_prefix or "").strip("/")
                if base and rel.startswith(base + "/"):
                    rel = rel[len(base) + 1:]
                ov = dict(target_relative_path=rel or None, partition_columns=d.partition_columns,
                          file_format=d.file_format, compression=d.compression, write_mode=d.write_mode)
                _log(f"vínculo #{l.id} (ctrl {l.control_id}): {d.name} -> {gen.name} + {ov}")
                if APPLY:
                    l.destination_id = gen.id
                    l.target_relative_path = rel or None
                    l.partition_columns = d.partition_columns
                    l.file_format, l.compression, l.write_mode = d.file_format, d.compression, d.write_mode
                    l.updated_at = datetime.now(timezone.utc)

        # 3) Inativar (soft) os destinos específicos/legados (não-genéricos, não-template).
        generic_ids = {g.id for g in generic.values() if g.id}
        for d in dests.values():
            if d.id in generic_ids or d.is_template or not d.active:
                continue
            _log(f"inativar destino específico: {d.name} (#{d.id})")
            if APPLY:
                d.active = False
                d.deleted_at = datetime.now(timezone.utc)
                d.deleted_by = "migrate_destinations_to_generic"

        if APPLY:
            db.commit()
            print("OK: migração aplicada.")
        else:
            db.rollback()
            print("DRY-RUN concluído (nada foi gravado). Rode com --apply para efetivar.")


if __name__ == "__main__":
    main()
