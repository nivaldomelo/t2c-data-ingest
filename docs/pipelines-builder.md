# Pipelines — Builder visual (DAG de jobs)

Monte pipelines conectando **jobs** já cadastrados numa **DAG** visual (React Flow) e execute em
ordem topológica, com o resultado de cada job liberando (ou pulando) os próximos.

## Conceitos

- **Pipeline**: um conjunto nomeado de steps + dependências (uma DAG).
- **Step**: um nó da DAG, vinculado a um job. Tem `run_if`, retry, timeout, parâmetros, ativo.
- **Dependência**: uma aresta `upstream → downstream` com `dependency_type`:
  `success` (padrão — roda o próximo só se o anterior teve sucesso), `finished`, `failed`, `always`.

## Como usar

1. **Pipelines → Novo pipeline** (nome, descrição, grupo) → abre a tela de detalhe.
2. Aba **Builder**: arraste jobs da lateral para o canvas, conecte-os arrastando entre as
   bolinhas dos nós (saída laranja → entrada), clique num nó/aresta para editar no painel, e
   clique **Salvar** (`PUT /pipelines/{id}/graph`). Use **Validar** para checar antes.
3. Aba **Execuções**: histórico de execuções do pipeline; clique numa execução para ver o
   **status por step** (timeline) e abrir os **logs** do job de cada step.
4. **Executar pipeline** (topo): valida e dispara (`POST /pipelines/{id}/run`).

## Validações (antes de salvar/executar)

Pelo menos um job; sem **ciclo/dependência circular** (mensagem ex.: *"dependência circular:
clientes → pedidos → clientes"*); jobs existentes; alerta para jobs inativos; sem conexão
duplicada; pelo menos um job inicial (sem upstream); alerta para nós soltos.

## Execução (ordem topológica)

`POST /pipelines/{id}/run` cria uma `pipeline_executions` e um `pipeline_step_executions` por
step (pending). Os steps **raiz** (sem upstream) são enfileirados como execuções de job normais
(`trigger_type=pipeline`) e rodam no worker. A cada tick, o worker **avança** o pipeline:
quando um job termina, o step vira `success`/`failed`; steps cujos upstreams tiveram sucesso são
liberados; se um upstream falha, o downstream (dep. `success`) fica `skipped`. O pipeline
finaliza como `success`, `failed` ou `partial_success`. A arquitetura já suporta paralelismo
(vários steps prontos são liberados juntos).

## Permissões

`ingest:pipelines:read` (todos), `:write` (admin, editor), `:builder` (editar o graph — admin,
editor), `:run` (admin, editor, data_owner), `:delete` (admin). Auditoria: `PIPELINE_CREATED/
UPDATED/DELETED/GRAPH_UPDATED/EXECUTION_STARTED`.

## Exemplo pronto: `pipeline_massa_teste_postgres_to_mysql`

Seed idempotente (após os jobs `postgres_to_mysql_massa_teste_*`):

```bash
docker compose exec api python scripts/seed_massa_teste_pipeline.py
```

DAG: `clientes → pedidos → {itens_pedido, pagamentos} ; pagamentos → eventos_status`. Executa
as cargas Postgres→MySQL na ordem correta. Endpoints:
`GET/PUT /api/v1/pipelines/{id}/graph`, `POST /api/v1/pipelines/{id}/validate`,
`POST /api/v1/pipelines/{id}/run`, `GET /api/v1/pipelines/{id}/executions`,
`GET /api/v1/pipeline-executions/{id}` e `/steps`.
