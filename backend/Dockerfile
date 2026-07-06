# T2C Data Ingest backend — mirrors the Turn2C standard (non-root uid 1001, explicit COPY).
# Includes a JRE + spark-submit client so the worker can submit jobs to the Spark cluster.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    postgresql-client \
    openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1001 appuser && useradd --uid 1001 --gid 1001 --create-home appuser

COPY requirements.txt pyproject.toml ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install pyspark==3.5.1

COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY src ./src
COPY scripts ./scripts

RUN pip install . \
    && apt-get purge -y --auto-remove build-essential \
    && chown -R appuser:appuser /app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/liveness', timeout=3)"

USER 1001

CMD ["uvicorn", "t2c_ingest.main:app", "--host", "0.0.0.0", "--port", "8000"]
