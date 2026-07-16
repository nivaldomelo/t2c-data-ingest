# {{ job_name }}

{{ job_description }}

## Tipo

- Engine: {{ engine }}
- Job type: {{ job_type }}
- Template: {{ template_name }}

## Controle de Ingestão

- Controle: {{ control_name }}
- Grupo: {{ control_group }}
- Tipo de ingestão: {{ ingestion_type }}
- Coluna incremental: {{ incremental_column }}

## Origem

- Origem: {{ source_name }}
- Tipo: {{ source_type }}
- Database: {{ source_database }}
- Schema: {{ source_schema }}
- Tabela: {{ source_table }}

## Destino principal

- Destino: {{ primary_destination_name }}
- Tipo: {{ primary_destination_type }}
- Schema: {{ primary_target_schema }}
- Tabela: {{ primary_target_table }}
- Write mode: {{ primary_write_mode }}
- Chaves: {{ primary_key_columns }}
- Staging: {{ staging_table }}

## Cópia Data Lake

- Destino: {{ datalake_destination_name }}
- Bucket: {{ datalake_bucket }}
- Path: {{ datalake_target_path }}
- Formato: {{ file_format }}
- Compressão: {{ compression }}
- Partições: {{ partition_columns }}

## Execução

O worker resolve o Controle e injeta a configuração; rode pelo T2C Data Ingest ou:

```bash
{{ run_command }}
```

## Observações de segurança

- Não inserir senhas ou tokens no código.
- Não logar dados sensíveis.
- Usar sempre as Origens e Destinos cadastrados.
- Secrets são resolvidos pelo backend/worker em tempo de execução.
