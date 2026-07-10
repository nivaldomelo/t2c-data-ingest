# T2C Data Ingest Spark 4 runtime image — Spark 4.1.2 / Java 17 / Scala 2.13 / Python 3.10.
# Master, workers, driver and executors ALL use this same image, so the Python environment
# (interpreter + libraries) is identical everywhere. Jobs + libs + JDBC jars are baked in, so
# a fresh container/pod (local Docker or Kubernetes) runs without any live install.
#
# NOTE: the official Spark 4.1.2 Ubuntu image ships Python 3.10 (not 3.11). 3.10 is fully
# supported by Spark 4 and by every library used here; installing 3.11 is not viable on arm64
# (no deadsnakes packages). See docs/migracao-spark4.md.
FROM apache/spark:4.1.2-scala2.13-java17-python3-ubuntu

USER root

# ── JDBC drivers (baked so jobs never need --packages / network at run time) ──
ARG POSTGRES_JDBC=42.7.10
ARG MYSQL_JDBC=9.1.0
RUN set -eux; \
    cd /opt/spark/jars; \
    curl -fSL -o "postgresql-${POSTGRES_JDBC}.jar" \
      "https://repo1.maven.org/maven2/org/postgresql/postgresql/${POSTGRES_JDBC}/postgresql-${POSTGRES_JDBC}.jar"; \
    curl -fSL -o "mysql-connector-j-${MYSQL_JDBC}.jar" \
      "https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/${MYSQL_JDBC}/mysql-connector-j-${MYSQL_JDBC}.jar"

# ── Python runtime libraries (driver + executors share these) ──
COPY requirements.txt /opt/t2c/runtime/requirements.txt
RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python3 -m pip install --no-cache-dir -r /opt/t2c/runtime/requirements.txt

COPY conf/spark-defaults.conf /opt/spark/conf/spark-defaults.conf

# Driver + executors use the SAME interpreter.
ENV PYSPARK_PYTHON=/usr/bin/python3
ENV PYSPARK_DRIVER_PYTHON=/usr/bin/python3
ENV PYTHONUNBUFFERED=1

RUN mkdir -p /tmp/spark-local /tmp/spark-events && chown -R spark:spark /tmp/spark-local /tmp/spark-events /opt/t2c

USER spark

EXPOSE 7077 8080 8081
