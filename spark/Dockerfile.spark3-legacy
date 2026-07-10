# T2C Data Ingest Spark cluster image — Spark 3.5.1 + JDBC drivers (Postgres/MySQL) + S3A.
# Master and worker use the SAME image; the command is set in docker-compose.
# Mirrors the t2c-data-spark image so jobs behave identically across products.
FROM apache/spark:3.5.1

USER root

ARG POSTGRES_JDBC=42.7.10
ARG MYSQL_JDBC=9.1.0
ARG HADOOP_AWS=3.3.4
ARG AWS_SDK_BUNDLE=1.12.262

RUN set -eux; \
    cd /opt/spark/jars; \
    curl -fSL -o "postgresql-${POSTGRES_JDBC}.jar" \
      "https://repo1.maven.org/maven2/org/postgresql/postgresql/${POSTGRES_JDBC}/postgresql-${POSTGRES_JDBC}.jar"; \
    curl -fSL -o "mysql-connector-j-${MYSQL_JDBC}.jar" \
      "https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/${MYSQL_JDBC}/mysql-connector-j-${MYSQL_JDBC}.jar"; \
    curl -fSL -o "hadoop-aws-${HADOOP_AWS}.jar" \
      "https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/${HADOOP_AWS}/hadoop-aws-${HADOOP_AWS}.jar"; \
    curl -fSL -o "aws-java-sdk-bundle-${AWS_SDK_BUNDLE}.jar" \
      "https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/${AWS_SDK_BUNDLE}/aws-java-sdk-bundle-${AWS_SDK_BUNDLE}.jar"

COPY conf/spark-defaults.conf /opt/spark/conf/spark-defaults.conf

# Python DB drivers used by the DRIVER side of jobs (e.g. reading the control table via psycopg,
# MySQL upsert via pymysql). Baked here so the driver — which runs INSIDE a Spark container when
# submitting via docker exec — has the same libs as the executors. Versions are py3.8-compatible.
RUN python3 -m pip install --no-cache-dir "psycopg[binary]>=3.1,<3.2" "pymysql>=1.1,<1.2"

RUN mkdir -p /tmp/spark-local /tmp/spark-events && chown -R 185:185 /tmp/spark-local /tmp/spark-events

USER 185

EXPOSE 7077 8080 8081
