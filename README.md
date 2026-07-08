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

### Detalhe do job (abas)

Clique no nome de um job (ou em **Ver detalhes**) para abrir `/jobs/{id}`, com abas:

- **Visão geral** — tipo, engine, script, conexões origem/destino, parâmetros padrão,
  timeout, retry, criador, última execução, último status e tempo médio.
- **Execuções** — apenas as execuções daquele job, com filtros (status, data inicial/final,
  usuário, busca na mensagem) e paginação de 25. Clique numa execução para abrir o detalhe.
- **Código** — **editor estilo VS Code** (Monaco): tema escuro, numeração de linhas,
  syntax highlight, badge de linguagem, **Copiar**, **Recarregar** e **Salvar**. Veja abaixo.
- **Configurações** — argumentos e chaves de variáveis de ambiente (valores ocultados).

Endpoints: `GET /api/v1/jobs/{id}`, `GET /api/v1/jobs/{id}/executions`
(`page,page_size,status,date_from,date_to,user_id,search`), `GET /api/v1/jobs/{id}/code`.

### Editor de código (visualizar, editar e salvar)

A aba **Código** é um editor Monaco (mesma base do VS Code): tema escuro, syntax highlight,
numeração de linhas, minimap, indicador de **alterações não salvas**, confirmação ao sair com
alterações pendentes e alerta amigável quando o conteúdo contém possíveis credenciais
(`password=`, `senha=`, `secret=`, `token=`, `access_key`, `secret_key`).

- **Visualizar:** requer `ingest:jobs:code:read`. O cabeçalho mostra arquivo, caminho,
  linguagem detectada, última modificação, tamanho e o modo (leitura ou edição).
- **Editar/Salvar:** requer `ingest:jobs:code:write`. **Salvar** (`PUT /api/v1/jobs/{id}/code`)
  fica desabilitado sem alterações e destacado em laranja quando há mudanças. Sem permissão de
  escrita, o editor abre em **somente leitura**.
- **Recarregar** recarrega o arquivo do servidor (descarta alterações locais após confirmação).

**Extensões editáveis:** `.py .sql .sh .yaml .yml .json .txt` (`JOB_CODE_EDITABLE_EXTENSIONS`).
Extensões sensíveis (`.env .pem .key .crt .p12 .jks .properties .ini`) **nunca** são editáveis.

**Backups e histórico:** antes de sobrescrever, é criada uma cópia em
`JOB_CODE_BACKUP_DIR` (padrão `/opt/t2c/backups/job-code`, montado de `./backups`) no formato
`{job_id}_{arquivo}_{timestampUTC}.bak`. Cada salvamento grava uma linha em
`t2c_data_ingest.job_code_versions` (hashes/tamanhos antes/depois, autor, resumo) e um evento
`JOB_CODE_UPDATED` em `t2c_data_ingest.audit_events`.

**Controle de conflito (optimistic lock):** a leitura devolve `last_modified_at`; o
salvamento envia esse valor em `expected_last_modified_at`. Se o arquivo mudou nesse meio-tempo,
a API retorna erro tratado: *"Este arquivo foi alterado por outro usuário ou processo.
Recarregue o código antes de salvar."*

**Segurança de caminho.** O backend só serve/edita arquivos **dentro dos diretórios permitidos**
(`ALLOWED_SCRIPT_DIRS`, padrão `/opt/t2c/spark/jobs`, `/opt/t2c/python_jobs`, `/opt/spark/jobs`,
`/app/jobs`). O caminho é resolvido com `realpath` — path traversal (`../`), caminhos fora da
allowlist (`/etc/passwd`) e arquivos inexistentes retornam erro amigável.

**Boas práticas:** nunca coloque senhas/tokens no código. Use as **Conexões** cadastradas
(resolvidas em tempo de execução) ou variáveis de ambiente seguras — o editor alerta ao detectar
padrões de credencial, mas a responsabilidade final é do autor.

Permissões: `ingest:jobs:code:read` (admin, editor, data_owner, stewardship) e
`ingest:jobs:code:write` (admin, editor). Viewer não acessa o código.

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

## Schedules (agendamento de jobs)

Jobs podem ser executados automaticamente em horários agendados (estilo Airflow). Há uma
tela geral **Schedules** no menu e uma aba **Agendamentos** no detalhe do job.

- **Criar/editar:** nome, tipo (`cron/hourly/daily/weekly/monthly/manual`), expressão cron,
  timezone (padrão `America/Sao_Paulo`), início/fim opcionais, parâmetros e ativo. Há
  **templates rápidos** (a cada 15 min, de hora em hora, seg–sex 08:00, etc.) que preenchem o
  cron, e um botão **Validar cron** que mostra as **próximas 5 execuções**.
- **Ações:** ativar/inativar, executar agora, ver execuções (histórico de disparos), remover.
- Um schedule `manual` não dispara sozinho (sem `next_run_at`).

**Scheduler (container separado — `scheduler`).** Não roda no backend web. A cada
`SCHEDULER_POLL_INTERVAL_SECONDS` (padrão 30s) ele reivindica schedules vencidos
(`active` e `next_run_at <= now`) com `SELECT ... FOR UPDATE SKIP LOCKED` (dois schedulers
nunca disparam o mesmo), enfileira uma execução (`trigger_type=schedule`,
`triggered_by=system_scheduler`, `schedule_id`), grava um `schedule_runs` (único por
`schedule_id + scheduled_for` → idempotente), atualiza `last_run_at`/`last_status` e
**recalcula `next_run_at` a partir de agora** — se ficou parado, dispara o slot vencido uma
vez e segue para o próximo, **sem criar centenas de execuções atrasadas**. Se `end_at` passou,
o schedule é finalizado (inativado). Cálculo de horário via `croniter` respeitando a timezone.

As execuções agendadas aparecem normalmente na aba **Execuções** do job; no detalhe da
execução aparece *Disparado por: Schedule*, o nome do agendamento, o horário previsto e o de
disparo.

Endpoints: `GET/POST /api/v1/job-schedules`, `GET/PUT/DELETE /api/v1/job-schedules/{id}`,
`POST /api/v1/job-schedules/{id}/{enable,disable,run}`, `GET /api/v1/job-schedules/{id}/runs`,
`POST /api/v1/job-schedules/validate-cron`, `GET/POST /api/v1/jobs/{job_id}/schedules`,
`GET /api/v1/job-schedules/summary`.

Permissões: `ingest:schedules:read` (todos os perfis), `:write` (admin, editor), `:delete`
(admin), `:enable`/`:disable` (admin, editor), `:run` (admin, editor, data_owner). Auditoria:
`JOB_SCHEDULE_CREATED/UPDATED/ENABLED/DISABLED/DELETED/TRIGGERED/FAILED`.

Exemplos de cron: `*/15 * * * *` (15 min), `0 * * * *` (de hora em hora), `0 8 * * 1-5`
(seg–sex 08:00), `0 8-18 * * 1-5` (seg–sex, de hora em hora, 08–18h), `0 0 * * *` (meia-noite).

## Controle de Ingestão

Área administrativa para cadastrar os **parâmetros das tabelas** que serão processadas pelos
jobs/pipelines. Os registros ficam em **`controle.t2c_data_controle_ingestao`** (schema
`controle`, não duplicado no `t2c_data_ingest`). A migration cria o schema e a tabela de forma
**não-destrutiva** (`IF NOT EXISTS`) — dados existentes são preservados.

Cada registro descreve uma tabela a ingerir:
- **Identificação:** `nome_tabela` (obrigatório), `grupo`, `tipo_tabela`, `ativo`, `observacao`.
- **Origem/destino:** `origem` (MYSQL/POSTGRES/…), `destino` (BRONZE/SILVER/GOLD/…), `origem_id`
  (id livre ou de uma **conexão cadastrada** — o form oferece um combo com as conexões).
- **Estratégia:** `tipo_ingestao` (FULL/INCREMENTAL/CDC/D-1/MANUAL), `coluna_data`,
  `coluna_ultima_alteracao`, `colunas_chave` (ex.: `id,order_id`), `watermark_atual`.
- **Sensibilidade:** `dados_sensiveis` (ex.: `cpf,email,telefone`).
- **Execução:** `status`, `ultima_execucao` (o scheduler/jobs atualizam no futuro).

Como usar:
- **Full:** defina `tipo_ingestao=FULL`; watermark não é necessário.
- **Incremental:** `tipo_ingestao=INCREMENTAL` + `coluna_ultima_alteracao` (ou `coluna_data`) e,
  quando houver histórico, `watermark_atual`; use `colunas_chave` para o merge/upsert.
- **Ativar/inativar** controla se a tabela entra nas próximas ingestões.
- Filtre/consulte por grupo, origem, destino, status, tipo e busca textual.

Uso futuro: jobs e pipelines poderão referenciar um registro (campo opcional
`ingestion_control_id` já disponível no job) para obter nome da tabela, origem/destino, tipo de
ingestão, colunas de watermark/chave, dados sensíveis e status — sem hardcode no script.

Endpoints: `GET/POST /api/v1/ingestion-control`, `GET/PUT/DELETE /api/v1/ingestion-control/{id}`,
`POST /api/v1/ingestion-control/{id}/{activate,deactivate}`, `GET /api/v1/ingestion-control/summary`.
Permissões: `ingest:control:read` (todos os perfis), `:write` (admin, editor), `:delete`
(admin). Auditoria: `INGESTION_CONTROL_CREATED/UPDATED/DELETED/ACTIVATED/DEACTIVATED`.

## Variáveis

Parâmetros reutilizáveis para jobs/pipelines (evitam valores fixos no código). Ficam em
`t2c_data_ingest.variables`. Cada job recebe as variáveis como **variáveis de ambiente** no
runtime (`os.getenv("NOME")`), tanto para Python quanto Spark.

- **Tipos:** `string, integer, decimal, boolean, date, datetime, json, secret`.
- **Escopo:** `global, job, pipeline, environment` (vínculo a job/pipeline preparado via
  `job_variables`, uso futuro). **Ambiente:** `local, dev, hml, prd` (ou vazio = global).
- **Nome** é normalizado para formato de código (`bucket bronze` → `BUCKET_BRONZE`).
- **Como usar:** o detalhe da variável tem a aba **Como usar** com exemplos prontos em
  **Python** e **Spark** (editor estilo VS Code), além de `GET /api/v1/variables/{id}/usage-examples`.

**Variáveis secretas** (`is_secret` ou tipo `secret`): o valor é **criptografado** em repouso
(Fernet, mesma chave das Conexões) e **nunca** retornado pela API (aparece como `********`);
ao editar, valor em branco mantém o atual; o valor real nunca vai para logs nem auditoria.
Para **credenciais de banco**, prefira a tela **Conexões**; use variáveis secretas apenas para
segredos de parâmetros de execução.

Endpoints: `GET/POST /api/v1/variables`, `GET/PUT/DELETE /api/v1/variables/{id}`,
`POST /api/v1/variables/{id}/{activate,deactivate}`, `GET /api/v1/variables/{id}/usage-examples`,
`GET /api/v1/variables/summary`. Permissões: `ingest:variables:read` (todos), `:write`
(admin, editor), `:delete` (admin), `:secret:write` (admin, editor), `:secret:read` (admin).
Auditoria: `VARIABLE_CREATED/UPDATED/DELETED/ACTIVATED/DEACTIVATED/SECRET_UPDATED`.

> **Boas práticas:** não coloque senha/token no código. Use **Conexões** para bancos e
> **Variáveis** para parâmetros de execução (datas, buckets, flags, limites).

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
