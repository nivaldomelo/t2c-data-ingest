# T2C Data Ingest

Camada **operacional** de ingestão, execução, orquestração e processamento de dados —
complementar ao **t2c_data** (catálogo, governança, qualidade e controle). Inspirado em
Databricks + Airflow, começando local com **Docker + Spark** e preparado para evoluir para
Kubernetes/EKS.

## Como complementa o t2c_data

| t2c_data (plataforma) | t2c_data_ingest (operação) |
| --- | --- |
| Catálogo, Explorer, Data Quality, Certificação, Privacidade, Owners, Domínios, Produtos de dados, Dashboard executivo | Pipelines de ingestão, Jobs Python/Spark, Execuções, Logs, Clusters, Migração Airflow |
| **Dono** de usuários, perfis, autenticação e permissões base | **Reaproveita** autenticação/usuários do t2c_data; define permissões próprias `ingest:*` |

Princípios:

- **Nasce separado, mas integrado.** Projeto próprio, banco compartilhado, schema próprio.
- **Sem duplicar usuários.** Valida o mesmo JWT do t2c_data e lê `users`/`roles`/`permissions`
  do schema `t2c_data` (somente leitura).
- **O backend não executa carga pesada.** Ele registra, valida permissão, cria a execução
  `queued` e enfileira. O trabalho roda no **worker** (jobs Python) ou no **cluster Spark**.

## Arquitetura local

```
                +-------------------+
   navegador -> |  frontend (Vite)  |  :3001
                +---------+---------+
                          | /api
                +---------v---------+        +------------------+
                |  api (FastAPI)    | :8010  |  Postgres (t2c)  |
                |  registra/enfileira| <----> |  schema:         |
                +---------+---------+        |  t2c_data_ingest |
                          |                  |  lê: t2c_data    |
                 status/logs                 +------------------+
                          |
     +--------------------v---------------------+
     |  worker (jobs Python + spark-submit)     |
     +---------------------+--------------------+
                           |  spark://spark-master:7077
              +------------v-----------+
              | spark-master + worker  |  :8090 (UI)
              +------------------------+
```

## Containers

| Serviço | Descrição | Porta host |
| --- | --- | --- |
| `frontend` | UI Vite/React (nginx) | 3001 |
| `api` | Backend FastAPI (registra/valida/orquestra) | 8010 |
| `worker` | Executa jobs Python e submete jobs Spark | — |
| `spark-master` | Spark master | 7078 / UI 8090 |
| `spark-worker` | Spark worker (2 cores, 2G) | UI 8091 |
| `postgres` | Opcional (`--profile with-db`) se você não tiver o Postgres do t2c_data | 5433 |

As portas são deslocadas das do t2c_data para os dois stacks rodarem lado a lado.

## Banco de dados

Mesma instância Postgres do t2c_data. O ingest cria e é dono do schema:

```sql
CREATE SCHEMA IF NOT EXISTS t2c_data_ingest;
```

Tabelas (schema `t2c_data_ingest`): `clusters`, `job_definitions`, `pipeline_definitions`,
`pipeline_steps`, `executions`, `execution_logs`, `execution_artifacts`,
`runtime_parameters`, `airflow_dag_imports`, `airflow_task_imports`, `audit_events`.

As tabelas de usuários/perfis do t2c_data **não são duplicadas** — são lidas do schema
`t2c_data` pelo módulo `auth_bridge`.

## Como subir o ambiente

1. Crie o arquivo de ambiente do backend e ajuste os valores:

   ```bash
   cp backend/.env.example backend/.env
   ```

   **Importante:** `JWT_SECRET_KEY` deve ser **idêntico** ao do backend do t2c_data para os
   tokens serem aceitos. `DATABASE_URL` deve apontar para o Postgres existente (em Docker,
   use `host.docker.internal`).

2. Suba tudo:

   ```bash
   docker compose up --build
   ```

   O serviço `api` aplica as migrations (`alembic upgrade head`) e registra o cluster
   "Spark Local Docker" automaticamente.

   Não tem o Postgres do t2c_data rodando? Suba o embutido:

   ```bash
   docker compose --profile with-db up --build
   # e ajuste DATABASE_URL para o host "postgres" em backend/.env
   ```

3. Acesse:
   - Frontend: http://localhost:3001
   - API (docs): http://localhost:8010/docs
   - Spark master UI: http://localhost:8090

### Login

O login é um **proxy** para o t2c_data (`T2C_DATA_AUTH_BASE_URL`): as credenciais são
encaminhadas, o t2c_data emite o JWT e o ingest passa a validá-lo. Alternativamente, faça
login no t2c_data e reutilize o token.

## Como testar o Spark

- UI do master: http://localhost:8090 — deve listar 1 worker ativo.
- Em Clusters, use **Testar conexão** para validar o alcance ao master.

## Como criar e executar um job

1. **Jobs → criar** (ou `POST /api/v1/jobs`). Exemplo de job Python:
   - tipo `python`, script `/opt/t2c/python_jobs/examples/hello_ingest.py`.
   Exemplo Spark:
   - tipo `spark_python`, script `/opt/spark/jobs/bronze/ingestao_clientes.py`,
     cluster "Spark Local Docker".
2. **Executar** (`POST /api/v1/jobs/{id}/run`) — cria uma execução `queued`.
3. O **worker** captura a execução, roda (`python` ou `spark-submit`), grava logs e status.
4. Acompanhe em **Execuções** e veja os logs no detalhe.

## Conexões (bancos de dados)

O item de menu **Conexões** gerencia conexões PostgreSQL/MySQL reutilizáveis por jobs e
pipelines. Ficam no schema próprio `t2c_data_ingest.connections`.

- **Cadastrar/editar:** informe tipo (PostgreSQL sugere porta `5432`, MySQL `3306`), host,
  banco, schema, usuário, senha, SSL e parâmetros extras (JSON).
- **Testar:** `POST /api/v1/connections/{id}/test` abre a conexão real e roda `SELECT 1`
  (psycopg para Postgres, pymysql para MySQL), atualizando `last_test_status`
  (`success`/`failed`/`not_tested`), `last_test_message` e `last_tested_at`.
- **Segurança da senha:** armazenada **criptografada** (Fernet, chave `CONNECTION_SECRET_KEY`
  — cai no `JWT_SECRET_KEY` em dev). A API **nunca** retorna a senha; listagens/detalhes
  expõem apenas `has_password`. Ao editar, senha em branco **mantém** a atual.
- Jobs têm um campo opcional `connection_id` (ainda não obrigatório) já preparado para
  vincular uma conexão cadastrada.

Um job pode referenciar conexões cadastradas pelos argumentos `--source-connection` /
`--target-connection` (por **nome ou id**). O worker resolve, valida (ativa), testa a
conectividade, descriptografa a senha e injeta as credenciais por variável de ambiente
(`SOURCE_*` / `TARGET_*`) — nunca em linha de comando nem em log. Exemplo completo de job
Spark MySQL→PostgreSQL: [docs/job-payments-mysql-to-postgres.md](docs/job-payments-mysql-to-postgres.md).

Endpoints: `GET /api/v1/connections`, `GET /api/v1/connections/{id}`,
`POST /api/v1/connections`, `PUT /api/v1/connections/{id}`,
`DELETE /api/v1/connections/{id}`, `POST /api/v1/connections/{id}/test`,
`GET /api/v1/connections/summary`.

> Os endpoints seguem o prefixo padrão do produto (`/api/v1/...`), consistente com as demais
> áreas (jobs, pipelines, execuções).

## Permissões (`ingest:*`)

Derivadas dos perfis existentes do t2c_data, sem conceder privilégio administrativo indevido:

| Perfil | Permissões |
| --- | --- |
| admin | todas |
| editor | read, write, run, logs:read, clusters:read, airflow:read, connections:read/write/test |
| viewer | read, logs:read, connections:read |
| stewardship | read, logs:read, connections:read |
| data_owner | read, run, logs:read, connections:read/test |

Permissões de conexões: `ingest:connections:read`, `ingest:connections:write`,
`ingest:connections:test`, `ingest:connections:delete` (delete é exclusivo de admin).

## Migração do Airflow (gradual)

O módulo **Airflow legado** nasce como **inventário**, não migração automática. As DAGs de
produção continuam no Airflow; aqui elas são cadastradas, analisadas e mapeadas para
pipelines novos, com status de migração controlado. Veja [docs/airflow-migration.md](docs/airflow-migration.md).

## Estrutura do repositório

```
t2c-data-ingest/
├── backend/         # FastAPI (src/t2c_ingest), Alembic, worker, Dockerfile
├── frontend/        # Vite + React + Tailwind + React Query
├── spark/           # imagem do cluster, conf, jobs Spark, jars, data
├── python_jobs/     # jobs Python (ex.: examples/)
├── docs/            # documentação
└── docker-compose.yml
```

## Roadmap

- **Fase 1 — Fundação (esta entrega):** stack local, schema+migrations, auth reaproveitada,
  dashboard, clusters, jobs, execuções, logs, inventário Airflow.
- **Fase 2 — Execução real:** worker executando Python e `spark-submit`, retry/timeout/cancelamento.
- **Fase 3 — Pipelines:** steps ordenados, parada em erro, reprocesso por step, timeline.
- **Fase 4 — Airflow:** migração de DAG piloto e padrão oficial de novas ingestões.
- **Fase 5 — Cloud/EKS:** Spark on Kubernetes, S3, secrets manager, CI/CD.
