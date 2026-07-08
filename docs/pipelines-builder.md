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
2. Clique em **Abrir Builder** — abre um **modal amplo centralizado** (95vw × 90vh) estilo grafo
   do Airflow, mais moderno.

### No builder (modal)

- **Header**: nome, status, nº de jobs/conexões, última execução, indicador **"não salvo"** e
  botões **Validar / Organizar / Salvar / Executar / Fechar**. Fechar com alterações pendentes
  pede confirmação.
- **Sidebar de jobs**: busca + adicionar ao canvas.
- **Canvas**: minimap, controles (zoom/fit), pan, arrastar nós. Criar conexões de 3 formas:
  1. **arrastar** da bolinha de saída (laranja, à direita) para a entrada de outro nó;
  2. **+ no nó** (aparece no hover) → escolhe o próximo job, que é adicionado à direita e já
     conectado;
  3. selecionar e editar no **painel de propriedades**.
- **Organizar layout**: reorganiza os nós em camadas da esquerda para a direita (dagre),
  facilitando pipelines grandes.
- **Painel de propriedades** (direita): edita step (nome, run_if, retry, timeout, ativo) ou a
  conexão (tipo de dependência); em execução, mostra status/logs do step.
- **Painel inferior** com abas **Validações / Execução (timeline) / Logs**.

### Cores (nós e conexões)

Nós: `queued/pending` cinza · `running` laranja (pulsando) · `success` verde · `failed` vermelho
· `skipped` cinza claro · `timeout` âmbar · `cancelled` cinza. Conexões: `waiting` cinza ·
`released` laranja · `success` verde · `blocked` vermelho · `skipped` cinza.

### Modo edição x acompanhamento

Ao clicar **Executar**, o builder entra em **modo acompanhamento**: a edição estrutural é
bloqueada, e o grafo atualiza sozinho (polling de `GET /pipeline-executions/{id}/graph-status`
a cada 3s até o status final) colorindo nós e conexões. Clique num nó para ver status e logs do
step (`/step/{step_execution_id}/logs`). A aba **Execução** mostra a linha do tempo
(`/timeline`). Toast final indica sucesso / falha / sucesso parcial.

> `Salvar` só no modo edição (`PUT /pipelines/{id}/graph`, valida antes). Posições dos nós são
> persistidas; na reabertura o layout salvo é carregado (ou use **Organizar**).

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
