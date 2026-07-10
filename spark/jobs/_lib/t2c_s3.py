"""S3 / Data Lake helpers for Spark and Python jobs.

The worker (backend/scripts/run_worker.py -> worker_support._inject_s3) injects, per role
(SOURCE_/TARGET_), the non-secret S3 config as env vars and the AWS credentials as the standard
AWS_* env vars (never on the command line). The S3A filesystem confs (endpoint/region/path-style/
ssl) are passed to spark-submit as --conf. So inside a job you only need to:

  * build the canonical s3a path for a table/partition -> build_s3_path / s3_path_for_role
  * (for pure-Python jobs) get a boto3 client that already points at the right endpoint/region
    using the env credentials -> s3_client_from_env

Path standard (matches the spec):
    s3a://{bucket}/{base_prefix}/{tabela}/ano=YYYY/mes=MM/dia=DD/
"""
from __future__ import annotations

import os
from datetime import date, datetime


def _clean(part: str) -> str:
    """Trim slashes/whitespace from a single path segment. Blocks path traversal ('..')."""
    p = (part or "").strip().strip("/")
    if ".." in p.split("/"):
        raise ValueError(f"segmento de caminho inválido (traversal): {part!r}")
    return p


def _join(*parts: str) -> str:
    return "/".join(_clean(p) for p in parts if _clean(p))


def build_s3_path(
    bucket: str,
    base_prefix: str,
    tabela: str,
    *,
    when: date | datetime | None = None,
    scheme: str = "s3a",
    partitioned: bool = True,
) -> str:
    """Build the canonical data-lake path for a table.

    ``s3a://{bucket}/{base_prefix}/{tabela}/ano=YYYY/mes=MM/dia=DD/`` when ``partitioned`` and a
    date is given (defaults to today's UTC date); otherwise ``s3a://{bucket}/{base_prefix}/{tabela}/``.
    """
    if not bucket:
        raise ValueError("bucket é obrigatório para montar o caminho S3")
    body = _join(base_prefix, tabela)
    if partitioned:
        d = when or datetime.now().date()
        if isinstance(d, datetime):
            d = d.date()
        body = _join(body, f"ano={d.year:04d}", f"mes={d.month:02d}", f"dia={d.day:02d}")
    return f"{scheme}://{bucket}/{body}/"


def role_s3_config(role: str = "TARGET") -> dict:
    """Read the role-prefixed S3 config the worker injected (bucket/prefix/region/endpoint/layer)."""
    p = role.upper().rstrip("_") + "_"
    return {
        "bucket": os.environ.get(f"{p}S3_BUCKET", ""),
        "base_prefix": os.environ.get(f"{p}S3_PREFIX", ""),
        "region": os.environ.get(f"{p}S3_REGION", ""),
        "endpoint_url": os.environ.get(f"{p}S3_ENDPOINT", ""),
        "default_layer": os.environ.get(f"{p}S3_LAYER", ""),
    }


def s3_path_for_role(
    tabela: str,
    role: str = "TARGET",
    *,
    when: date | datetime | None = None,
    partitioned: bool = True,
) -> str:
    """Canonical s3a path for a table using the bucket/prefix of the given connection role."""
    cfg = role_s3_config(role)
    return build_s3_path(
        cfg["bucket"], cfg["base_prefix"], tabela, when=when, partitioned=partitioned
    )


def s3_client_from_env(role: str = "TARGET"):
    """boto3 S3 client using the standard AWS_* env creds, pointed at the role's endpoint/region.

    For pure-Python jobs. Spark jobs use the S3A filesystem (paths from build_s3_path) directly.
    """
    import boto3  # baked into the image

    cfg = role_s3_config(role)
    kwargs: dict = {}
    if cfg["region"]:
        kwargs["region_name"] = cfg["region"]
    if cfg["endpoint_url"]:
        kwargs["endpoint_url"] = cfg["endpoint_url"]
    # Credentials come from AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/AWS_SESSION_TOKEN (or the
    # instance/role provider chain when those are absent) — boto3 resolves them automatically.
    return boto3.client("s3", **kwargs)
