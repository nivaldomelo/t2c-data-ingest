# Job Spark — payments (MySQL → PostgreSQL)

Copia a tabela de pagamentos do MySQL para o PostgreSQL usando Spark, com carga **full
upsert por id** (a origem não tem `updated_at`).

- **Job:** `mysql_payments_to_postgres_spark_payments` (tipo `spark_python`, engine Spark)
- **Script:** `/opt/t2c/spark/jobs/mysql_to_postgres/payments_mysql_to_postgres.py`
- **Origem:** conexão `mysql_1` → `software_test_lab.payments`
- **Destino:** conexão `postgres_1` → `andromeda`, schema `spark`, tabela `payments`
  (staging `spark.stg_payments_ingest`)

## Objetivo e fluxo

1. Lê a tabela MySQL via JDBC (apenas as colunas necessárias).
2. Normaliza tipos (id/order_id BIGINT, amount DECIMAL(12,2), installment_count INTEGER,
   paid_at/created_at TIMESTAMP, enums como STRING).
3. Valida os enums (`payment_method`, `payment_status`); linhas com valor inválido são
   descartadas e o total é reportado.
4. Grava em uma **staging** `spark.stg_payments_ingest` (colunas VARCHAR para os enums).
5. Faz **UPSERT** staging → `spark.payments` com casts explícitos
   (`payment_method::spark.payment_method_enum`, `payment_status::spark.payment_status_enum`)
   e `ON CONFLICT (id) DO UPDATE`.
6. Ao final imprime `INGEST_SUMMARY: read=… valid=… invalid=… upsert=…`, capturado no
   histórico da execução (mensagem final + artefato).

## Segurança das credenciais

- **Nada é hardcodado.** O script lê as credenciais de variáveis de ambiente
  `SOURCE_*` (MySQL) e `TARGET_*` (PostgreSQL).
- O **worker** resolve as conexões cadastradas (`mysql_1`/`postgres_1`) a partir dos
  argumentos `--source-connection` / `--target-connection`, valida se existem e estão
  **ativas**, **testa a conectividade**, **descriptografa** a senha (Fernet) e injeta as
  credenciais por **env var** — nunca por linha de comando e **nunca em log**.
- Referência por **nome ou id** (ex.: `--source-connection mysql_1` ou `--source-connection 3`).

## Pré-requisitos

1. Cadastrar em **Conexões**:
   - `mysql_1` (MySQL) apontando para o banco de origem.
   - `postgres_1` (PostgreSQL) apontando para `andromeda` (schema `spark`).
2. No PostgreSQL de destino, o job garante automaticamente (idempotente, **não recria** se já
   existir): o schema `spark`, os tipos `spark.payment_method_enum` / `spark.payment_status_enum`,
   a tabela final `spark.payments` (conforme o DDL do projeto) e a staging
   `spark.stg_payments_ingest` (VARCHAR nos enums, truncada a cada execução). Se preferir criar
   você mesmo:
   ```sql
   CREATE SCHEMA IF NOT EXISTS spark;
   CREATE TYPE spark.payment_method_enum AS ENUM ('PIX','CREDIT_CARD','DEBIT_CARD','BANK_SLIP','CASH');
   CREATE TYPE spark.payment_status_enum AS ENUM ('PENDING','AUTHORIZED','PAID','FAILED','REFUNDED','CHARGEBACK');
   ```

> Observações da carga: valores de ENUM do MySQL podem vir preenchidos com espaços via JDBC;
> o job aplica `trim()` antes de validar/gravar. Uma `--source-table` qualificada
> (`software_test_lab.payments`) define o banco de origem, independente do banco da conexão.
3. Drivers JDBC: o worker adiciona automaticamente via `--packages`
   (`org.postgresql:postgresql`, `com.mysql:mysql-connector-j`) quando não há jars locais em
   `./spark/jars`. A imagem do cluster Spark já traz ambos em `/opt/spark/jars`.

## Como executar pelo T2C Data Ingest

1. Semear o job (idempotente):
   ```bash
   docker compose exec api python scripts/seed_payments_job.py
   ```
2. Em **Jobs**, localize `mysql_payments_to_postgres_spark_payments` e clique **Executar**
   (ou `POST /api/v1/jobs/{id}/run`). A execução entra como `queued`; o worker resolve as
   conexões, testa, submete o Spark e atualiza status/logs.
3. Acompanhe em **Execuções** → abra a execução para ver **timeline**, **logs** e o resumo.

## Como executar manualmente via spark-submit

Dentro de um container com Spark e os drivers (ex.: `spark-master`), com as credenciais
exportadas como env (nunca em texto no comando):

```bash
export SOURCE_HOST=... SOURCE_PORT=3306 SOURCE_DB=software_test_lab SOURCE_USER=... SOURCE_PASSWORD=...
export TARGET_HOST=... TARGET_PORT=5432 TARGET_DB=andromeda TARGET_USER=... TARGET_PASSWORD=...

spark-submit \
  --master spark://spark-master:7077 \
  --jars /opt/spark/jars/mysql-connector-j.jar,/opt/spark/jars/postgresql.jar \
  /opt/t2c/spark/jobs/mysql_to_postgres/payments_mysql_to_postgres.py \
  --source-connection mysql_1 \
  --target-connection postgres_1 \
  --source-table software_test_lab.payments \
  --target-schema spark \
  --target-table payments \
  --staging-table stg_payments_ingest
```

> Pelo worker do T2C Data Ingest você **não** precisa exportar nada: ele injeta `SOURCE_*`/
> `TARGET_*` a partir das conexões cadastradas.

## Validar a carga

```sql
SELECT count(*) FROM spark.payments;
SELECT payment_status, count(*) FROM spark.payments GROUP BY 1 ORDER BY 2 DESC;
SELECT * FROM spark.payments ORDER BY id DESC LIMIT 10;
```
Compare com a origem: `SELECT count(*) FROM software_test_lab.payments;`

## Consultar logs

- **UI:** Execuções → abrir a execução → área de logs (terminal) + resumo `INGEST_SUMMARY`.
- **API:** `GET /api/v1/executions/{id}` (detalhe + logs) e `GET /api/v1/executions/{id}/logs`.

## Tratar erro de enum no PostgreSQL

`invalid input value for enum spark.payment_method_enum: "XPTO"` significa que a staging tem
um valor fora do domínio. O job já **descarta** linhas com enum inválido antes da carga e
reporta a contagem (`invalid=N`). Se o erro persistir:

- Confira se os `CREATE TYPE ... ENUM` contêm **todos** os valores esperados.
- Verifique a linha `AVISO: N linha(s) com enum inválido foram descartadas` nos logs.
- Ajuste a origem ou os enums de destino conforme necessário.
