# Arquitetura — T2C Data Ingest

## Objetivo

Plataforma operacional para gerenciar **pipelines de ingestão** e **processamento** de dados,
com suporte a jobs **Spark** e **Python**, integração com **PostgreSQL** e **Data Lake**,
inventário do **Airflow legado** e reaproveitamento da **autenticação/autorização** do
t2c_data.

## Separação de responsabilidades

- **t2c_data** — catálogo, governança, qualidade, observabilidade, controle e a base de
  identidade (usuários, perfis, autenticação, permissões).
- **t2c_data_ingest** — cadastro e execução de jobs/pipelines, histórico e logs de execução,
  clusters, parâmetros e a migração gradual das DAGs do Airflow.

## Fluxo de execução (por que o backend não faz carga pesada)

1. Usuário dispara um job/pipeline pela API.
2. A API **valida permissão** (`ingest:run`), cria a execução com status `queued` e persiste
   os parâmetros efetivos (`runtime_parameters`).
3. O **worker** reivindica a execução (`SELECT ... FOR UPDATE SKIP LOCKED`), marca `running`,
   executa fora do processo web:
   - `python` → `python script.py`
   - `spark_python` / `spark_submit` → `spark-submit --master spark://spark-master:7077`
4. stdout/stderr viram `execution_logs`; ao final grava `success`/`failed`/`timeout`, duração
   e mensagem.

Esse contrato (`queued → running → success/failed`) não muda quando trocarmos o worker
single-process por uma fila real (Celery/Redis) ou por Jobs no Kubernetes.

## Autenticação (auth_bridge)

- Mesmo **JWT HS256** do t2c_data (segredo compartilhado via `JWT_SECRET_KEY`).
- `get_current_user` decodifica o token (`sub`=email, `tv`=token_version) e lê o usuário e os
  papéis do schema `t2c_data` — **somente leitura**, via uma metadata SQLAlchemy separada
  (`ReferenceBase`), fora do controle do Alembic do ingest.
- As permissões `ingest:*` são **derivadas** dos papéis existentes (ver
  `features/auth_bridge/permissions.py`). Nenhuma tabela nova de usuário/papel é criada.

## Banco / schemas

- Engine com `search_path = t2c_data_ingest, t2c_data, public`.
- Modelos do ingest: `Base.metadata = MetaData(schema="t2c_data_ingest")`.
- Migrations Alembic criam o schema e gerenciam **apenas** objetos do schema do ingest
  (filtro `include_object`/`include_name` por schema).

## Preparação para cloud/EKS

- Worker desacoplado do web → vira Deployment/Job escalável.
- Cluster com `type` (`local_docker` → `kubernetes`/`eks`/`emr`) já modelado.
- Spark image com hadoop-aws + aws-sdk para S3A (Data Lake) já incluída.
