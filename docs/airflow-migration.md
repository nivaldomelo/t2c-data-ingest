# Migração do Airflow — estratégia gradual

> **Regra de ouro:** não substituir o Airflow agora. O ingest nasce em paralelo, novas
> ingestões começam nele, e as DAGs antigas são migradas aos poucos e com controle.

```
Airflow atual (produção)
        ↓
T2C Data Ingest nasce em paralelo
        ↓
Novas ingestões começam nele
        ↓
DAGs antigas são inventariadas   ← este módulo
        ↓
Uma DAG piloto é migrada
        ↓
Migração acontece aos poucos
```

## O módulo nasce como inventário

O módulo **Airflow legado** (`features/airflow_migration`) **não move nem executa** DAGs de
produção. Ele registra e acompanha a migração:

- Cadastro da DAG: nome, descrição, schedule atual, tags, caminho do arquivo.
- Tasks da DAG (operador, dependências) para mapear 1:1 com steps de pipeline.
- **Status de migração**: `nao_analisada`, `em_analise`, `migracao_planejada`,
  `migrada_parcialmente`, `migrada`, `descontinuada`.
- Mapeamento DAG → pipeline novo (`mapped_pipeline_id`) e task → step (`mapped_step_id`).
- Observações técnicas por DAG/task.

## Passo a passo sugerido

1. **Inventariar** as DAGs atuais (cadastro manual ou importação futura).
2. **Analisar** cada DAG e planejar o pipeline equivalente no ingest.
3. **Migrar uma DAG piloto**, validando execução, logs e reprocesso.
4. **Definir o padrão oficial** para novas ingestões (sempre no ingest).
5. Atualizar o status até `migrada`/`descontinuada`.

## Permissões

- `ingest:airflow:read` — visualizar o inventário (admin, editor).
- `ingest:airflow:migrate` — cadastrar/atualizar DAGs e mapeamentos (admin).
