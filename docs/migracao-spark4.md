# Migração para Apache Spark 4

Branch: `feature/spark4-python311-runtime`.

## Stack alvo (real)

| Componente | Versão |
|---|---|
| Apache Spark | **4.1.2** |
| Java | **17** |
| Scala | **2.13** |
| Python (driver + executores) | **3.10** |

> **Nota sobre Python:** a imagem oficial `apache/spark:4.1.2-scala2.13-java17-python3-ubuntu`
> traz **Python 3.10** (Ubuntu 22.04), não 3.11. Python 3.10 é totalmente suportado pelo Spark 4
> e por todas as bibliotecas do projeto (pandas 2.2, pyarrow, numpy, sqlalchemy 2, psycopg 3,
> pymysql, boto3). Forçar 3.11 não é viável em arm64 (sem pacotes deadsnakes) e não traz ganho
> prático. O projeto padroniza **Python 3.10**.

## Como funciona

- **Imagem única** `t2c-data-ingest-spark-runtime:local` (também taggeada `:4.1.2-python3.10`),
  construída de `spark/Dockerfile`. Master, workers, driver e executores usam a MESMA imagem →
  o Python do driver é idêntico ao dos executores.
- **Libs e JDBC bakeados**: `spark/requirements.txt` (pandas/pyarrow/numpy/requests/sqlalchemy/
  psycopg/pymysql/boto3) + jars Postgres/MySQL em `/opt/spark/jars`. Nada é instalado em
  container vivo.
- **Submissão**: o worker submete os jobs via `docker exec` dentro de um container Spark
  (driver = Python 3.10 dos executores), com `spark.pyspark.python=/usr/bin/python3`.
- **Versões rastreadas**: cada execução grava `spark_version`/`python_version`/`runtime_image`;
  a tela Clusters mostra Spark/Python/Java/Scala.

## Subir o ambiente local

```bash
docker compose build spark-worker-1          # constrói a imagem Spark 4 (:local)
docker compose up -d spark-master spark-worker-1 spark-worker-2 spark-worker-3
docker compose up -d api worker scheduler frontend
docker exec -i t2c-data-ingest-api-1 alembic upgrade head   # migração 0024 (colunas de versão)
```

## Validar

**Versões na imagem:**
```bash
docker exec t2c-data-ingest-spark-worker-1-1 bash -lc \
  'python3 --version; java -version; /opt/spark/bin/spark-submit --version'
```
Esperado: Python 3.10.x, Java 17, Spark 4.1.2 (Scala 2.13).

**Execução distribuída + libs (3 workers):**
```bash
docker exec t2c-data-ingest-spark-worker-1-1 bash -lc \
  '/opt/spark/bin/spark-submit --master spark://spark-master:7077 \
   --conf spark.driver.host=$(hostname) --conf spark.pyspark.python=/usr/bin/python3 \
   /opt/t2c/spark/jobs/system/validate_spark4_runtime.py'
```
Esperado: `OK: Spark 4.1.2, 3 workers, libs OK em todos.` (falha com exit != 0 se < 3 workers
ou alguma lib não importar num executor).

**Job real:** rodar um job de ingestão pela plataforma e conferir `status=success` +
`INGEST_SUMMARY` + `spark_version=4.1.2` na execução.

## Diagnóstico rápido

| Sintoma | Causa provável | Ação |
|---|---|---|
| `Python in worker has different version` | driver e executor com Pythons diferentes | garantir submit via container (SPARK_SUBMIT_VIA_CONTAINER=true) |
| `ModuleNotFoundError` num executor | lib não bakeada | adicionar em `spark/requirements.txt` e rebuildar a imagem |
| `No suitable driver` (JDBC) | jar ausente | conferir `/opt/spark/jars` (postgres/mysql) na imagem |
| `< 3 workers` na validação | worker não registrou | `docker compose ps`, logs do master (`:8090`) |
| erro de cast/ANSI SQL | Spark 4 usa ANSI por padrão | revisar o job; se necessário `spark.sql.ansi.enabled=false` no job |

## Rollback (voltar para Spark 3.5.1)

O Dockerfile Spark 3 está preservado em `spark/Dockerfile.spark3-legacy`.

**Opção A — via branch (recomendado):**
```bash
git checkout develop
docker compose build spark-worker-1
docker compose up -d spark-master spark-worker-1 spark-worker-2 spark-worker-3
```

**Opção B — reconstruir a imagem legacy sem trocar de branch:**
```bash
docker build -f spark/Dockerfile.spark3-legacy -t t2c-data-ingest-spark-runtime:spark3-legacy ./spark
docker tag t2c-data-ingest-spark-runtime:spark3-legacy t2c-data-ingest-spark-runtime:local
docker compose up -d spark-master spark-worker-1 spark-worker-2 spark-worker-3
```
Depois, revalidar (`validate_spark4_runtime` mostrará Spark 3.5.1) e reexecutar jobs críticos.
O histórico de execuções registra qual runtime rodou cada job (`spark_version`/`runtime_image`).

## Preparação para Kubernetes / EKS

A mesma imagem versionada é usada no cluster K8s (driver + executores = pods da imagem).
Exemplo em `deploy/k8s/spark-job-example.yaml`. Pontos-chave:
- push da imagem para um registry (em vez de `docker tag` local);
- `--master k8s://…`, `--deploy-mode cluster`, `spark.kubernetes.container.image=<imagem>`;
- novos pods já sobem com libs + jobs + jars (tudo bakeado);
- a validação distribuída roda como um K8s Job usando a mesma imagem.
