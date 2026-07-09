# Ingestão controlada PostgreSQL → MySQL (dirigida pela tabela de controle)

Job Spark genérico que **não tem tabelas hardcoded**: ele lê os parâmetros de
`controle.t2c_data_controle_ingestao` e processa as tabelas ativas configuradas como
`origem=POSTGRES` e `destino=MYSQL`.

- **Script:** `/opt/t2c/spark/jobs/postgres_to_mysql/postgres_to_mysql_controlled_ingest.py`
- **Origem:** conexão `postgres_1` (schema `massa_teste`)
- **Destino:** conexão `mysql_1` (database `massa_teste`)
- **Jobs cadastrados:** `postgres_to_mysql_massa_teste_all` (grupo inteiro) e um por tabela
  (`_clientes`, `_pedidos`, `_itens_pedido`, `_pagamentos`, `_eventos_status`).

## O que o job faz

1. Lê os registros de controle (`--control-group massa_teste` ou `--table-name massa_teste.x`),
   filtrando `ativo`, `origem=POSTGRES`, `destino=MYSQL`.
2. Para cada tabela: marca `status=EM_EXECUCAO`, lê a origem via JDBC, normaliza tipos
   (boolean→`0/1`, UUID→string, numeric/decimal preservados, timestamp→datetime), garante a
   tabela destino e a **staging** no MySQL (`CREATE TABLE IF NOT EXISTS` + `stg LIKE final`),
   escreve na staging e faz **upsert** `INSERT … ON DUPLICATE KEY UPDATE` pela chave.
3. Em sucesso: `status=SUCESSO`, `ultima_execucao`, `observacao` e — só quando houve dados —
   `watermark_atual` = maior valor incremental processado.
4. Em erro: `status=ERRO` + `observacao` resumida (o stack trace completo vai só para os logs
   da execução); **o watermark NÃO é alterado**.

### FULL vs INCREMENTAL

- **INCREMENTAL:** coluna = `coluna_ultima_alteracao` (senão `coluna_data`); se `watermark_atual`
  é nulo, faz carga inicial completa; senão filtra `WHERE coluna > watermark`. Sem coluna
  incremental → erro controlado.
- **FULL:** lê tudo e faz upsert pela chave (não apaga o destino).

## Segurança

Credenciais **nunca** ficam no código nem em log. O worker resolve `--source-connection` e
`--target-connection`, valida que estão ativas, testa conectividade, descriptografa as senhas
(Fernet) e injeta como env `SOURCE_*` / `TARGET_*`. A tabela de controle é lida via
`DATABASE_URL` (a base do ingest), herdada do worker.

## Como executar

Pelo T2C Data Ingest: **Jobs → `postgres_to_mysql_massa_teste_all` → Executar** (ou os
individuais). Acompanhe em **Execuções** (logs + `INGEST_SUMMARY`). Também dá para **agendar**
pelo módulo **Schedules**.

Seed dos parâmetros de controle + jobs (idempotente):

```bash
docker compose exec api python scripts/seed_postgres_to_mysql.py
```

Via spark-submit (dentro de um container com Spark + drivers), com credenciais em env:

```bash
spark-submit --master spark://spark-master:7077 \
  --jars /opt/spark/jars/postgresql.jar,/opt/spark/jars/mysql-connector-j.jar \
  /opt/t2c/spark/jobs/postgres_to_mysql/postgres_to_mysql_controlled_ingest.py \
  --control-group massa_teste --source-connection postgres_1 --target-connection mysql_1
# ou uma tabela:
#  --table-name massa_teste.clientes --source-connection postgres_1 --target-connection mysql_1
```

## Validar a carga

```sql
-- MySQL destino
SELECT count(*) FROM massa_teste.clientes;
-- controle (watermark/status)
SELECT nome_tabela, status, watermark_atual, ultima_execucao
FROM controle.t2c_data_controle_ingestao WHERE destino='MYSQL';
```

Uma segunda execução sem novos dados lê 0 linhas (o `watermark` já cobre o histórico) e **não
duplica** (upsert por chave).

## Drivers JDBC

O worker adiciona `--packages` (postgresql + mysql-connector-j) quando não há jars locais; a
imagem do cluster Spark também traz ambos em `/opt/spark/jars`.
