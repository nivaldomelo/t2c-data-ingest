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

A listagem de **Jobs** é uma **grade de cards paginada** (server-side), pensada para ~mil jobs:

- **Cards de resumo** no topo: total, Spark, Python, ativos e falhas recentes (7 dias) —
  agregações globais em `GET /api/v1/jobs/summary`.
- **Card por job** com ícone da engine (⚡ Spark laranja · 🐍 Python azul), nome, descrição (2
  linhas), tipo·engine, `origem → destino`, tags (3 + `+N`), status ativo, **última execução**
  (badge + data) e **tempo médio de sucesso**. Ações: **Abrir**, **Executar** e menu (⋯) com
  **Abrir código** (workspace), **Editar** e **Excluir** — cada uma respeitando permissões.
- **Filtros** (server-side): busca (nome/descrição/tipo/engine/tags/argumentos), engine, tipo,
  ativo/inativo, último status e tags; **ordenação** (nome, mais recentes, atualizados, última
  execução, mais executados); **tamanho de página** (12/24/48/96, padrão 24) e paginação
  "Mostrando X–Y de N · Página P de T". Alternância **Cards | Tabela**.

Performance: a lista faz uma única varredura agregada de execuções (última execução, contagem e
data por job) e resolve tags/conexões/tempo-médio em lote (sem N+1); índices em
`name`/`engine`/`type`/`is_active`/`deleted_at`.

### Criar um job (Novo Job)

Na tela **Jobs**, o botão **Novo Job** (canto superior direito; só aparece com
`ingest:jobs:create` — admin/editor) abre um modal guiado:

1. **Engine** — escolha **Spark** (jobs distribuídos: PySpark, Spark SQL, spark-submit) ou
   **Python** (scripts leves no worker da aplicação).
2. **Tipo** — filtrado pela engine: Spark → `spark_python`/`spark_sql`/`spark_submit`;
   Python → `python`.
3. **Formulário** — nome (recomendado `snake_case`), descrição, **script path** ou **Criar
   workspace automaticamente** (gera `main.py`/`main.sql` versionado com `utils/` e, no Spark,
   `sql/`), classe principal (spark-submit), cluster, conexões origem/destino/única (do módulo
   **Conexões**, com status do teste, sem senha), **argumentos** (construtor chave/valor que gera
   `--chave valor …`), parâmetros padrão (JSON), timeout, retry, ativo e **tags**.

Botões: **Criar job**, **Criar e abrir código** (abre o workspace do job) e **Criar e executar**
(dispara uma execução) — além de **Cancelar**. O backend valida: nome obrigatório e único entre
jobs ativos, **compatibilidade engine↔tipo** (`python_worker`→`python`;
`spark_cluster`→`spark_*`), `script_path` dentro dos diretórios permitidos, retry ≥ 0 e
permissão. Payload: `POST /api/v1/jobs` (com `tags` e `create_workspace`).

> Sobre **Criar workspace automaticamente**: o starter é provisionado no **diretório versionado**
> do job (`spark/jobs/{slug}` ou `python_jobs/{slug}`), não em `/opt/t2c/jobs/workspaces` —
> mantendo o princípio de que todo código de job é versionado no Git (deploy via imagem/K8s).

Clique no nome de um job (ou em **Ver detalhes**) para abrir `/jobs/{id}`, com abas:

- **Visão geral** — painel executivo em cards: **Resumo** (badges de tipo/engine/status, tags e
  script com copiar), **métricas** (total, último status, tempo médio de sucesso arredondado,
  última execução), **Última execução** (com atalho para o detalhe), **Saúde operacional**
  (status, taxa de sucesso, falhas recentes 7d, execuções em andamento, schedules ativos, com
  semáforo Boa/Atenção/Crítica), **Conexões** origem/destino (host:porta/database, teste e
  ações), **Configuração principal**, **Parâmetros e argumentos** (bloco de comando + “Ver
  estruturado”) e **Ações rápidas** (executar, ver execuções, abrir código, editar, agendar).
- **Execuções** — apenas as execuções daquele job, com filtros (status, data inicial/final,
  usuário, busca na mensagem) e paginação de 25. Clique numa execução para abrir o detalhe.
- **Código** — **editor estilo VS Code** (Monaco): tema escuro, numeração de linhas,
  syntax highlight, badge de linguagem, **Copiar**, **Recarregar** e **Salvar**. Veja abaixo.
- **Configurações** — organizada em cards: **Configuração principal** (tipo, engine, ativo,
  classe, script com copiar), **Execução** (cluster, timeout, retry, modo — com textos
  amigáveis para vazios), **Conexões** (origem/destino/única com host:porta/database, status do
  último teste e ações **Testar**/**Abrir conexão**, sem expor senha), **Argumentos** (bloco de
  comando com copiar + alternância “Ver estruturado”), **Variáveis de ambiente** (valores
  ocultados), **Tags** (badges + edição), **Metadados** e **Zona de perigo** (Excluir job). O
  botão **Editar configurações** abre o drawer/modal de edição.

Endpoints: `GET /api/v1/jobs/{id}`, `GET /api/v1/jobs/{id}/executions`
(`page,page_size,status,date_from,date_to,user_id,search`), `GET /api/v1/jobs/{id}/code`.

### Detalhe da execução (tela operacional)

`/executions/{id}` é uma tela em blocos, pensada para análise operacional:

- **Header** — nome, badge de status (Sucesso/Falha/Em execução…), `#id · Job|Pipeline ·
  tipo · engine`, gatilho (Manual/Agendamento/Pipeline/API/Retry) e início. Ações: **Copiar
  ID**, **Copiar logs**, **Abrir job**, **Abrir pipeline** e **Execução do pipeline** (quando
  veio de pipeline), **Reexecutar** (se permitido) e **Cancelar** (enquanto em execução).
- **Cards de resumo** — Status, Engine, Duração, Disparado por, **Lidos** e **Gravados**.
- **Linha do tempo** — Enfileirado / Início / Fim / Duração (com bloco de origem do
  agendamento ou do **pipeline**: pipeline, step e ordem).
- **Origem e destino** — conexões usadas (nome, tipo, host:porta/database e status do teste),
  **sem expor senhas**.
- **Resumo da ingestão** — interpreta a linha `INGEST_SUMMARY` (tabela, tipo, coluna
  incremental, watermarks, lidos/gravados, status). `watermark_novo=None` vira “watermark
  mantido”; linhas truncadas não quebram a tela.
- **Logs da execução** — viewer estilo terminal (fundo escuro, monoespaçado, altura mínima de
  500px) com **busca**, **quebra de linha**, **numeração**, **copiar**, **baixar**, **tela
  cheia** e destaque por conteúdo (OK/erro/warning/`spark-submit`/`INGEST_SUMMARY`).

Estados: sucesso com `lidos=0`/`gravados=0` mostra aviso informativo (não é erro); falha exibe
card de erro com mensagem, trace e **Copiar erro**; execução em andamento atualiza a cada 3s.

O backend enriquece `GET /api/v1/executions/{id}` com `execution_type`, `source_connection`,
`target_connection`, `ingest_summary`, `records_read/written` e o vínculo de pipeline
(`pipeline_name`, `pipeline_execution_id`, `step_name`, `step_order`) — parseados dos logs de
forma tolerante quando ainda não persistidos, sem alterar execuções antigas.

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
`/app/jobs`). O caminho é resolvido com `realpath` — path traversal (`../`), **caminhos
absolutos** (`/etc/passwd`) e caminhos fora da allowlist retornam erro amigável; a pasta raiz do
job nunca pode ser renomeada/excluída.

### Todo código é versionado (deploy via Git)

Não existe área de rascunho fora do Git. Ao **criar um job**, se você não informar um
`script_path`, o backend **provisiona** um arquivo inicial dentro de um diretório versionado,
conforme o tipo do job:

- `python` → `PYTHON_JOBS_DIR/{slug}/main.py` (padrão `/opt/t2c/python_jobs`, montado de `./python_jobs`)
- `spark_python` / `spark_submit` → `SPARK_JOBS_DIR/{slug}/main.py` (padrão `/opt/spark/jobs`, montado de `./spark/jobs`)
- `spark_sql` → `SPARK_JOBS_DIR/{slug}/main.sql`

O `{slug}` vem do nome do job (`{slug}-{id}` se já existir), garantindo uma pasta isolada por
job, com `main.*` de arranque e `README.md`. Um `script_path` informado explicitamente é aceito
somente se estiver dentro de um diretório permitido (senão, 403). Assim o código aparece na
árvore do repositório, é **commitado no GitHub** e entregue pelo CI/CD (futuro deploy em
Kubernetes) — a origem da verdade é sempre o Git.

### Workspace de código (estilo VS Code)

Na tela de **Detalhes do Job**, clicar na aba **Código** abre **diretamente** o workspace em um
modal grande (95vw × 90vh) — sem página intermediária. O arquivo principal (`script_path`) é
aberto automaticamente. Ao fechar, volta-se aos detalhes do job. É a mesma experiência de editor
multi-arquivo:

- **Explorador de arquivos** à esquerda: árvore do workspace do job com pastas expansíveis,
  criar arquivo/pasta, renomear e excluir (ações no hover). O workspace é **a pasta do script
  versionado do job** (em `spark/jobs` ou `python_jobs`); jobs sem script válido não abrem
  workspace (mensagem orientando a definir o caminho).
- **Abas** de arquivos abertos com indicador de não salvo e fechar por aba; **Ctrl/Cmd+S** salva
  a aba ativa; **Salvar todos** (barra superior) e **Copiar código**; barra de status com job,
  arquivo, tamanho e última modificação.
- **Endpoints:** `GET workspace/tree`, `GET/PUT/POST/DELETE workspace/file`,
  `POST/DELETE workspace/folder`, `PUT workspace/rename` (prefixo `/api/v1/jobs/{id}`).
- **Permissões:** `code:read` (ver/abrir), `code:write` (salvar), `code:create` (novo
  arquivo/pasta), `code:delete` (excluir), `code:rename` (renomear). Sem `code:write`, o
  workspace abre em somente leitura.
- **Extensões editáveis:** `.py .sql .sh .json .yaml .yml .md .txt`; sensíveis/binárias
  (`.env .pem .key .crt .p12 .jks .properties .ini .exe .jar .zip …`) são bloqueadas.
- **Backups + histórico + auditoria:** toda escrita/renomeação/exclusão faz backup em
  `JOB_CODE_BACKUP_DIR/{job_id}/` e grava uma linha em `job_code_versions` (com `action` e
  `file_path`) e um evento (`JOB_CODE_FILE_CREATED/UPDATED/RENAMED/DELETED`,
  `JOB_CODE_FOLDER_CREATED/DELETED`) — **sem** registrar o conteúdo do arquivo. O controle de
  conflito (`expected_last_modified_at`) e o alerta de credenciais valem também aqui.

**Boas práticas:** nunca coloque senhas/tokens no código. Use as **Conexões** cadastradas
(resolvidas em tempo de execução) ou variáveis de ambiente seguras — o editor alerta ao detectar
padrões de credencial, mas a responsabilidade final é do autor.

Permissões: `ingest:jobs:code:read` (admin, editor, data_owner, stewardship) e
`ingest:jobs:code:write` (admin, editor). Viewer não acessa o código.

### Editar e excluir job (soft delete + arquivamento de código)

O header dos **Detalhes do Job** traz **Executar**, **Editar**, **Excluir** e **Voltar**
(cada botão só aparece com a permissão correspondente).

**Editar** (`PUT`/`PATCH /api/v1/jobs/{id}`, permissão `ingest:write`) abre um modal com nome,
descrição, tipo, engine, `script_path`, conexões origem/destino, parâmetros padrão (JSON),
timeout, retry, tags e ativo/inativo. Valida nome obrigatório, tipo válido e **rejeita
`script_path` fora dos diretórios permitidos**; grava auditoria `JOB_UPDATED` e atualiza
`updated_by`.

**Excluir** (`DELETE /api/v1/jobs/{id}`, permissão `ingest:jobs:delete` — **admins** nesta
versão) faz **soft delete** e **nunca apaga o código**:

1. Verifica dependências ativas e **bloqueia** (HTTP 409) se o job estiver **em execução**,
   vinculado a **pipelines ativos** ou com **schedules ativos** (mensagem explicativa).
2. **Arquiva o código**: copia o workspace para
   `JOB_ARCHIVE_DIR/deleted_jobs/{id}_{slug}_{timestampUTC}/` (padrão `/opt/t2c/jobs/archive`,
   montado de `./archive`), com `workspace/`, `metadata.json` e `README_ARCHIVE.md`. A cópia é
   **validada** antes de remover o original; se o arquivamento falhar, a exclusão é abortada
   (nada é perdido).
3. **Marca** `deleted_at`/`deleted_by`/`delete_reason`/`archived_code_path`, seta `is_active=false`
   e remove o job da **listagem padrão** (use `?include_deleted=true` para incluí-los).
4. Registra auditoria `JOB_DELETE_REQUESTED` → `JOB_CODE_ARCHIVED` → `JOB_DELETED` (ou
   `JOB_DELETE_BLOCKED`) e uma linha em `job_code_versions` com `action=archived_on_job_delete`
   (sem conteúdo dos arquivos).

Acessar um job excluído mostra o aviso **"Este job foi excluído"** com o caminho do archive, a
data e o responsável — sem permitir executar/editar/abrir workspace (todos retornam 409).

Diretórios seguros permitidos (path traversal, caminhos absolutos e fora da allowlist são
bloqueados): `/opt/t2c/spark/jobs`, `/opt/t2c/python_jobs`, `/opt/spark/jobs`, `/app/jobs`,
`/opt/t2c/jobs/archive`.

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

Já existe um **job Spark dirigido pela tabela de controle** (PostgreSQL → MySQL) que lê esses
parâmetros e faz carga FULL/INCREMENTAL com staging + upsert, atualizando watermark/status —
ver [docs/job-postgres-to-mysql-controlled.md](docs/job-postgres-to-mysql-controlled.md).

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

## Tags

Tags organizam e facilitam a busca de jobs (estrutura normalizada `t2c_data_ingest.tags` +
`t2c_data_ingest.job_tags`). Um job pode ter várias tags; tags não são obrigatórias.

- **Tela Tags** (menu): listar/criar/editar/ativar-inativar/remover (remoção só se não estiver
  em uso), com contagem de jobs por tag. O **slug** é gerado do nome (acentos transliterados:
  `produção → producao`, `massa_teste → massa-teste`).
- **No job**: badges na **lista** (coluna Tags, com `+N`) e na **Visão geral**; edição na aba
  **Configurações** (autocomplete que cria tag ao digitar + Enter). `PUT /jobs/{id}/tags`
  aceita `{"tags":[...]}` — cria as inexistentes, sincroniza e remove vínculos ausentes.
- **Busca/filtro**: filtro por tags na lista (`GET /jobs?tags=spark,massa_teste`), e a busca do
  **Pipeline Builder** casa por nome, descrição **e tags** (`GET /jobs/search?search=&tags=`),
  exibindo as tags nos resultados.

Endpoints: `GET/POST /api/v1/tags`, `GET/PUT/DELETE /api/v1/tags/{id}`,
`POST /api/v1/tags/{id}/{activate,deactivate}`, `GET/PUT /api/v1/jobs/{id}/tags`.
Permissões: `ingest:tags:read` (todos), `:write` (admin, editor), `:delete` (admin),
`ingest:jobs:tags:write` (admin, editor). Auditoria: `TAG_*` e `JOB_TAGS_UPDATED`.
Seed inicial: `docker compose exec api python scripts/seed_tags.py`.

**Boas práticas:** tags curtas (`spark`, `mysql`, `postgres`, `incremental`, `bronze`,
`silver`, `gold`, `financeiro`); evite duplicidades conceituais (`postgres`/`postgresql`/`pg`).

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

## Bibliotecas (pacotes Python do cluster)

A tela **Bibliotecas** (`/libraries`) permite instalar, listar, reinstalar e remover pacotes
Python (PyPI) usados por jobs Spark/Python — de forma **controlada**, sem executar comandos
shell livres.

**Como funciona.** O usuário informa apenas **nome** e (opcional) **versão**; o backend valida,
monta o comando `pip` com segurança e enfileira uma **ação** (`cluster_library_actions`). O
worker do T2C Data Ingest processa a fila (`queued → running → success/failed`), executando
`pip` como **lista de argumentos** (nunca shell), com timeout, e captura stdout/stderr nos logs
da ação. Cada biblioteca vive em `cluster_libraries` com status
(`pending/queued/installing/installed/failed/removed`).

- **Instalar:** botão *Instalar biblioteca* → nome + versão (ou especificação avançada como
  `pandas>=2.2.0`). Validação ao vivo mostra o spec normalizado.
- **Detalhe (drawer):** abas **Resumo**, **Histórico**, **Logs** (terminal escuro) e **Como
  usar** (exemplos Python e Spark). Ações **Reinstalar** e **Remover**.
- **Endpoints:** `GET /libraries`, `GET /libraries/summary`, `GET /libraries/{id}`,
  `POST /libraries/install`, `POST /libraries/{id}/reinstall`, `POST /libraries/{id}/uninstall`,
  `GET /libraries/{id}/actions`, `GET /library-actions/{id}`, `GET /library-actions/{id}/logs`,
  `POST /libraries/validate-package`.

**Segurança.** Só PyPI. O nome é validado por whitelist e são **bloqueados** caracteres/sequências
perigosas (`;`, `&&`, `|`, `$`, crase, `..`, `://`, espaços) e instalação por **URL, Git ou
caminho local**. `pip` é sempre invocado via lista de argumentos com timeout — nunca `sh -c`.
Nenhum secret é exposto. Toda ação gera auditoria
(`CLUSTER_LIBRARY_INSTALL_REQUESTED/STARTED/SUCCEEDED/FAILED`, etc.).

**Onde instala (dev local).** A instalação ocorre no container **`t2c_data_ingest_worker`** — o
mesmo que roda os jobs Python e faz `spark-submit` (driver) — no *user site* (`pip --user`, pois
o processo roda como usuário não-root). Configurável por env: `LIBRARY_PIP_PYTHON` (apontar para
um virtualenv, ex. `/opt/t2c/venvs/ingest/bin/python`), `LIBRARY_PIP_USER`, `LIBRARY_INSTALL_TIMEOUT`.

**Cuidados / limites (v1):**
- **Executors Spark** (containers `spark-worker`) **não** recebem as libs automaticamente — apenas
  o driver/worker. Libs usadas dentro de UDFs nos executors podem exigir recriar a imagem dos
  workers Spark. O driver/`spark-submit` usa o Python do worker (que enxerga o `--user site`).
- As libs vivem no filesystem do container do worker; **recriar a imagem** (`docker compose build`)
  zera o `~/.local`. Para persistência/produção, aponte `LIBRARY_PIP_PYTHON` para um virtualenv em
  volume dedicado.
- Libs com **dependências nativas** complexas podem exigir pacotes de sistema (rebuild da imagem).

Permissões: `ingest:libraries:read` (todos os papéis), `ingest:libraries:install` /
`ingest:libraries:uninstall` (admin, editor) e `ingest:libraries:manage` (admin). Sem permissão de
instalação, o botão *Instalar biblioteca* não aparece; sem permissão de remoção, *Remover* não aparece.

Tabela `job_libraries` já criada para, no futuro, vincular bibliotecas obrigatórias a um job e
validar antes de executar (não é aplicado nesta versão para não impactar execuções existentes).

## Alertas e notificações

A tela **Alertas** (`/alerts`) envia eventos importantes para **Teams**, **Slack** ou **webhooks
genéricos**:

- **Canais**: nome, tipo, URL do webhook (armazenada **criptografada** com Fernet e sempre
  **mascarada** na API), **severidade mínima** (info/warning/critical) e **eventos** assinados
  (vazio = todos). Ações: **Testar** (envia uma notificação de teste), editar, excluir.
- **Histórico**: cada notificação com evento, severidade, canal, **status de entrega**
  (`pending/sent/failed` + HTTP), erro e **Reenviar** em caso de falha.

**Como dispara:** o worker cria notificações (`emit`) quando uma execução finaliza e as entrega
(`dispatch`) a cada tick. Gatilhos ativos hoje: **JOB_FAILED** (job falhou/timeout, crítico),
**JOB_ZERO_RECORDS** (carga com `lidos=0 gravados=0`, aviso) e **PIPELINE_FAILED** (pipeline
falhou/parcial). O payload é adaptado por tipo (MessageCard do Teams, blocos do Slack, JSON
genérico) e inclui **link para o detalhe** da execução. Eventos como cluster/worker/schema/runtime
já existem no modelo e podem ser ligados a gatilhos futuros.

Endpoints: `GET/POST/PATCH/DELETE /api/v1/alerts/channels[/{id}]`,
`POST /api/v1/alerts/channels/{id}/test`, `GET /api/v1/alerts/notifications`,
`POST /api/v1/alerts/notifications/{id}/resend`. Permissões: `ingest:alerts:read` (todos os
papéis) e `ingest:alerts:manage` (admin/editor). Nunca expõe a URL/secret do webhook.

## Dashboard operacional

A tela inicial (`/`) é um **dashboard operacional** com atualização automática (10s) via
`GET /api/v1/dashboard/operational`, para responder rápido "o que está rodando, o que falhou e o
que está atrasado":

- **KPIs**: rodando agora (jobs + pipelines), execuções hoje (ok/falha), falhas em 7 dias (jobs e
  pipelines com erro), tempo médio, registros **lidos**/**gravados** hoje.
- **Painéis**: Rodando agora, Falhas recentes, **Cluster Spark** (workers/cores/memória ao vivo),
  **Schedules atrasados** (`next_run_at` no passado, minutos de atraso) e próximos, **execuções
  por status** (7d), **cargas com zero registros** hoje, **acima do tempo normal**
  (duração > 1,5× a média do job) e últimas execuções — cada item linka para o detalhe.

Os registros (lidos/gravados/zero) vêm da linha `INGEST_SUMMARY` que o worker salva em
`final_message` — sem varrer logs em tempo de request; agregações e o scan de execuções do dia são
limitados (bounded) para manter a tela rápida.

## Reprocessamentos (backfill)

A tela **Reprocessamentos** (`/backfills`) permite reprocessar dados de forma **controlada e
rastreável**, reutilizando a máquina de execução (as execuções nascem com `trigger_type=backfill`):

- **Job** — reprocessa um job específico.
- **Pipeline** — reexecuta o pipeline; opcionalmente **a partir de um step** (os steps anteriores
  são marcados como reaproveitados e só o step escolhido + descendentes rodam).
- **Grupo de controle** — reprocessa todos os jobs vinculados (via `ingestion_control_id`) às
  tabelas de um `grupo` do Controle de Ingestão.
- **Tabela de controle** — idem para uma tabela específica.

Opções: **período** (`period_start`/`period_end`, injetados como parâmetros da execução) e
**reset de watermark** das tabelas do controle — este exige a permissão dedicada
`ingest:backfill:watermark` e é **auditado** (`WATERMARK_RESET`, com valor antigo/novo). Vazio =
reprocessar do zero. Cada reprocessamento vira um `backfill_run` com status roll-up
(`queued → running → success/partial/failed`) atualizado pelo worker conforme as execuções/pipeline
terminam, e lista as execuções geradas.

Endpoints: `GET/POST /api/v1/backfills`, `GET /api/v1/backfills/{id}`,
`GET /api/v1/pipelines/{id}/steps`. Permissões: `ingest:backfill:run` (admin/editor/data_owner) e
`ingest:backfill:watermark` (admin/editor). Eventos: `BACKFILL_REQUESTED/STARTED`, `WATERMARK_RESET`.

> Para o reprocessamento de **grupo/tabela** disparar jobs, os jobs precisam estar vinculados à
> linha de controle pelo campo `ingestion_control_id`. Sem vínculo, o reset de watermark é aplicado
> mas nenhum job é enfileirado (0 alvos).

## Clusters

A tela **Clusters** (`/clusters`) mostra os clusters Spark em **cards** com dados **ao vivo** do
Spark master (a API lê `GET {SPARK_MASTER}:8080/json/`), não contadores estáticos:

- **Cards de resumo**: total, ativos, **workers**, **cores** e **memória** somados dos workers
  vivos e última validação (`GET /api/v1/clusters/summary`).
- **Card por cluster**: nome, badge de status (Ativo/Inativo/Inacessível/Validando/Não validado),
  master URL, tipo, ambiente (Local Docker/Kubernetes), workers/cores/memória (ao vivo) e
  esperados, última verificação e validação. Ações: **Ver detalhes**, **Testar conexão**
  (`POST /clusters/{id}/test` — ping + refresh), **Ver workers**.
- **Detalhe (modal) com abas**: **Resumo**; **Workers** (lista ao vivo com status/cores/memória
  por worker + alerta quando há menos de 3 workers para execução distribuída); **Bibliotecas**
  (libs do runtime + validar nos workers); **Validações** (histórico + disparar validação de
  bibliotecas / execução distribuída, que reutilizam a fila de validações do runtime);
  **Configurações**.

Endpoints: `GET /clusters[/summary,/{id},/{id}/workers,/{id}/validations]`,
`POST /clusters/{id}/{test,validate-workers,validate-libraries,validate-distributed-execution}`,
`GET /cluster-validations/{id}/logs`. Colunas novas em `clusters`
(`expected_workers`, `last_checked_at`, `last_validation_status`, `runtime_image`,
`environment`) na migração 0015. Permissões: `ingest:clusters:read/test/validate/manage`.

> Os nomes dos workers (`spark-worker-1/2/3`) são resolvidos por DNS reverso do IP reportado
> pelo master; se indisponível, cai para o IP/label. Cores/memória refletem o cluster real (no
> local, 1 core / 1G por worker → 3 cores / 3G no total).

## Ambiente de Execução (runtime do cluster)

Para garantir que **bibliotecas e código dos jobs estejam iguais em todos os workers** (inclusive
novos pods no Kubernetes), o T2C Data Ingest não instala libs em containers vivos. Em vez disso
segue o modelo de produção:

```
Cadastro de bibliotecas → requirements.txt → build de imagem Docker versionada
→ deploy do cluster com essa imagem → driver + executors usando a MESMA imagem → validação distribuída
```

A tela **Ambiente de Execução** (`/runtime`) tem quatro abas:

1. **Bibliotecas** — manifesto das dependências Python (nome+versão, ativar/inativar, remover).
   Validadas pelo mesmo whitelist seguro das Bibliotecas (só PyPI).
2. **requirements.txt** — gerado automaticamente das libs ativas; botão **Criar build de imagem**.
3. **Builds do Runtime** — histórico versionado; status (`queued/building/success/failed/active/deprecated`),
   duração, **logs do build**, **requirements snapshot** e **Ativar** imagem.
4. **Validação do Cluster** — **Validar execução distribuída** e **Validar bibliotecas** (e “Validar
   tudo”), com resultado por worker.

### Como funciona o build

O worker monta um **contexto de build** (`RUNTIME_BUILD_CONTEXT_DIR`, montado de `./runtime-builds`)
com `Dockerfile`, `runtime/requirements.txt`, o **código dos jobs** (`spark/jobs`, `python_jobs`,
`spark/jars`) e um `jobs_snapshot.json`, e roda `docker build` contra o daemon do host (socket
montado no worker; em K8s isto vira um passo de CI). Segredos (`.env/.pem/.key/.crt`) são excluídos
via `.dockerignore` e do `copytree`. A imagem sai versionada:
`t2c-data-ingest-spark-runtime:<AAAAMMDD.HHMMSS>`. Base configurável em `RUNTIME_BASE_IMAGE`.

> **Python do driver × executors:** o PySpark exige a mesma versão de Python no driver e nos
> executors. A imagem base `apache/spark:3.5.x` traz **Python 3.8** — por isso as validações
> distribuídas submetem o `spark-submit` de dentro de um container Spark (via `docker exec`), e a
> imagem runtime deve ser usada por driver **e** workers.
>
> **Versões das bibliotecas (importante):** como a base é Python 3.8, **prefira cadastrar as libs
> sem fixar versão** — o `pip` respeita `Requires-Python` e resolve automaticamente a versão
> compatível (ex.: `pandas` → `2.0.3`, a última com wheel para 3.8). **Não** fixe uma versão que
> exige Python ≥3.9 (ex.: `pandas==2.2.3`), senão o build falha com “No matching distribution”.
> Para usar libs mais novas, é preciso uma base com Python ≥3.9 (`RUNTIME_BASE_IMAGE`); no
> Kubernetes isso é natural (imagem própria). Em Apple Silicon/arm64, o repositório *deadsnakes*
> não tem pacotes, então instalar outro Python na base exige build por fonte/conda.
>
> **As libs só chegam aos workers pela imagem:** cadastrar em *Bibliotecas* e clicar *Validar*
> **não instala** nada — é preciso **Criar build → Ativar → Aplicar aos workers** (na aba
> *Validação do Cluster* ou em *Clusters → detalhe → Bibliotecas → Aplicar imagem ativa*). Só
> então as libs ficam disponíveis em todos os executors e a validação fica verde.

### 3 workers locais + validação distribuída

O `docker-compose` sobe **`spark-worker-1/2/3`** (1 core cada, mesma imagem, `spreadOut` → um
executor por worker). As validações são jobs Spark reais em `spark/jobs/system/`:

- `validate_distributed_execution.py` — paraleliza N partições e confirma que **≥3 workers**
  processaram (falha se tudo rodar num só). Ex.: `spark-worker-1/2/3: 10 partições` cada.
- `validate_runtime_libraries.py` — importa as libs **nos executors** e reporta ausências por host
  (ex.: “`pyarrow` ausente em `spark-worker-3`”). É assim que se investiga lib faltando num worker.

Fluxo local ponta a ponta (validado): cadastrar libs → gerar `requirements.txt` → **Criar build**
(imagem versionada com libs+jobs) → **Ativar** → **Aplicar e validar** → **Validar execução
distribuída** (3 workers).

### Aplicar a imagem ativa aos workers (fechar o ciclo local)

Na aba **Validação do Cluster**, **Aplicar e validar** (`POST /api/v1/runtime/apply`, permissão
`ingest:runtime:activate`) faz o deploy local da imagem **ativa**: o worker do ingest re-tagueia a
imagem ativa para a tag usada pelos workers (`RUNTIME_WORKER_IMAGE_TAG`, padrão
`t2c-data-ingest-spark-runtime:local`) e **recria** os containers `spark-worker-1/2/3` com ela
(clonando binds/rede/portas/comando via `docker inspect`, preservando os labels do Compose para
que ele continue gerenciando-os), aguarda os workers registrarem no master e então roda a
**validação de bibliotecas** no cluster novo. Resultado esperado: as libs cadastradas passam a
estar disponíveis em **todos os workers** (verde). É o equivalente local a um *rolling update* de
imagem no Kubernetes. Validado ponta a ponta: após aplicar, `six`/`requests` disponíveis nos 3
workers, zero falhas.

### Kubernetes (futuro)

Driver e executors usam a **mesma imagem** versionada (push para o ECR); `executor.instances`
configurável; jobs e libs já dentro da imagem — nada de instalação manual após o pod subir. Um job
pode fixar `runtime_build_id` (coluna já criada) ou usar o runtime **ativo** por padrão.

Permissões: `ingest:runtime:read` (todos), `ingest:runtime:libraries:write`, `ingest:runtime:build`,
`ingest:runtime:activate` (admin) e `ingest:runtime:validate` (admin/editor/data_owner). Eventos de
auditoria: `RUNTIME_LIBRARY_ADDED/UPDATED/REMOVED`, `RUNTIME_BUILD_REQUESTED/STARTED/SUCCEEDED/FAILED/ACTIVATED`,
`RUNTIME_VALIDATION_STARTED/SUCCEEDED/FAILED`.

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
