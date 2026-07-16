"""{{ job_name }} — {{ job_description }}

Job Python leve, controlado pelo Controle de Ingestão do T2C Data Ingest (sem Spark).
Indicado para APIs (Jira, Mixpanel, Blip, REST genérica), validações e integrações leves.

O worker resolve Controle + Origens + Destinos e injeta (nunca em cmdline/log):
  * T2C_CONTROL_CONFIG      -> JSON (não-secreto) com origem + N destinos por papel/ordem
  * T2C_CONN_{id}_PASSWORD  -> senha de cada conexão de banco
  * AWS_*                   -> credenciais/endpoint do Data Lake
  * T2C_EXECUTION_ID        -> id da execução

Gerado a partir do template `python_controlled_job`. Implemente os pontos marcados com TODO
(read_source / write_*), mantendo leitura de config, logs e INGEST_SUMMARY.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.helpers import transform_records  # noqa: E402

JOB_NAME = "{{ job_name }}"
CONTROL_NAME = "{{ control_name }}"
CONTROL_GROUP = "{{ control_group }}"

log = logging.getLogger(JOB_NAME)


def parse_args():
    parser = argparse.ArgumentParser(description="{{ job_description }}")
    parser.add_argument("--control-id", required=False, default="{{ control_id }}")
    parser.add_argument("--control-name", required=False, default="{{ control_name }}")
    parser.add_argument("--control-group", required=False, default="{{ control_group }}")
    parser.add_argument("--execution-id", required=False)
    args, _ = parser.parse_known_args()
    return args


def _conn_password(conn_id) -> str:
    return os.environ.get(f"T2C_CONN_{conn_id}_PASSWORD", "")


def load_control_config(args):
    """Carrega os controles injetados pelo worker (T2C_CONTROL_CONFIG). Sem secrets aqui."""
    raw = os.environ.get("T2C_CONTROL_CONFIG")
    if not raw:
        raise RuntimeError("T2C_CONTROL_CONFIG ausente — o worker não resolveu a carga controlada.")
    controls = (json.loads(raw) or {}).get("controls", [])
    if not controls:
        raise RuntimeError("Nenhum controle na configuração injetada.")
    return controls


def read_source(control: dict) -> list:
    """Lê a origem. Ex.: REST API, Jira, Mixpanel, Blip, banco pequeno.

    A senha da conexão (se houver) está em T2C_CONN_{id}_PASSWORD; nunca faça hardcode.
    """
    source = control["source"]
    log.info("Lendo origem %s (%s)", source.get("source_type"), source.get("table"))
    # TODO: implementar a leitura conforme o tipo da origem de {{ control_name }}.
    return []


def write_primary_destination(records: list, control: dict) -> int:
    destination = next((d for d in control.get("destinations", []) if d.get("role") == "primary"), None)
    if not destination:
        log.info("Nenhum destino principal configurado.")
        return 0
    log.info("Gravando destino principal %s (%s)", destination.get("target_table"), destination.get("type"))
    # TODO: implementar a escrita conforme o tipo do destino.
    return len(records)


def write_datalake_copy(records: list, control: dict) -> int:
    datalake = next((d for d in control.get("destinations", []) if d.get("role") == "datalake_copy"), None)
    if not datalake:
        log.info("Nenhuma cópia Data Lake configurada.")
        return 0
    log.info("Gravando cópia Data Lake em %s", datalake.get("target_path"))
    # TODO: implementar escrita em JSON/Parquet conforme necessidade.
    return len(records)


def process_control(control: dict):
    status = "SUCESSO"
    records_read = records_primary = records_datalake = 0
    try:
        records = read_source(control)
        records_read = len(records)
        transformed = transform_records(records, control)
        records_datalake = write_datalake_copy(transformed, control)
        records_primary = write_primary_destination(transformed, control)
    except Exception:
        status = "ERRO"
        raise
    finally:
        print(
            "INGEST_SUMMARY: "
            f"job={JOB_NAME} table={control.get('nome_tabela')} tipo={control.get('tipo_ingestao')} "
            f"lidos={records_read} gravados_primary={records_primary} gravados_datalake={records_datalake} "
            f"status={status}",
            flush=True,
        )


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    try:
        for control in load_control_config(args):
            process_control(control)
    except Exception:
        log.exception("Falha na execução do job %s", JOB_NAME)
        raise


if __name__ == "__main__":
    sys.exit(main())
