"""Resolve a Data Lake catalog layout from an S3 connection's ``extra_params``.

Two modes (spec §4/§5):
  - ``layer_as_schema``: each configured layer (bronze/silver/gold) is a schema, possibly with
    its own bucket + base_prefix. If no ``layers`` are given, fall back to the connection's own
    bucket/prefix as a single schema named after ``default_layer`` (or "datalake").
  - ``prefix_as_schema``: the schemas are DISCOVERED at scan time as the first-level folders
    under ``bucket/base_prefix`` (returned here as a single root spec to expand).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LayerSpec:
    name: str            # schema name (e.g. "bronze")
    bucket: str
    base_prefix: str     # normalized, no leading/trailing slash
    layer_name: str | None = None


@dataclass
class CatalogConfig:
    enabled: bool
    mode: str                                   # layer_as_schema | prefix_as_schema
    default_file_format: str = "parquet"
    partition_pattern: str = "ano=YYYY/mes=MM/dia=DD"
    layers: list[LayerSpec] = field(default_factory=list)   # for layer_as_schema
    root: LayerSpec | None = None               # for prefix_as_schema (schemas discovered under it)


def _norm(prefix: str | None) -> str:
    return (prefix or "").strip().strip("/")


def resolve_catalog_config(conn) -> CatalogConfig:
    """Build a CatalogConfig from ``conn.extra_params``. Never raises; returns enabled=False when
    the connection has no catalog configuration."""
    ep = conn.extra_params or {}
    enabled = bool(ep.get("catalog_enabled", False))
    mode = ep.get("catalog_mode") or "layer_as_schema"
    fmt = ep.get("default_file_format") or "parquet"
    pattern = ep.get("partition_pattern") or "ano=YYYY/mes=MM/dia=DD"
    default_bucket = ep.get("bucket_name") or ""
    default_prefix = _norm(ep.get("base_prefix"))

    cfg = CatalogConfig(enabled=enabled, mode=mode, default_file_format=fmt, partition_pattern=pattern)

    if mode == "prefix_as_schema":
        cfg.root = LayerSpec(name="", bucket=default_bucket, base_prefix=default_prefix)
        return cfg

    # layer_as_schema
    raw_layers = ep.get("layers") or []
    layers: list[LayerSpec] = []
    for entry in raw_layers:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("name") or "").strip()
        bucket = entry.get("bucket") or default_bucket
        if not name or not bucket:
            continue
        layers.append(LayerSpec(
            name=name, bucket=bucket, base_prefix=_norm(entry.get("base_prefix")), layer_name=name,
        ))
    if not layers and default_bucket:
        # No explicit layers: treat the connection's bucket/prefix as one schema.
        name = (ep.get("default_layer") or "datalake").strip() or "datalake"
        layers.append(LayerSpec(name=name, bucket=default_bucket, base_prefix=default_prefix, layer_name=name))
    cfg.layers = layers
    return cfg


def config_summary(cfg: CatalogConfig) -> dict:
    """Non-secret, JSON-safe summary for passing to the scan job / showing in the UI."""
    return {
        "mode": cfg.mode,
        "default_file_format": cfg.default_file_format,
        "partition_pattern": cfg.partition_pattern,
        "layers": [
            {"name": l.name, "bucket": l.bucket, "base_prefix": l.base_prefix, "layer_name": l.layer_name}
            for l in cfg.layers
        ],
        "root": (
            {"bucket": cfg.root.bucket, "base_prefix": cfg.root.base_prefix} if cfg.root else None
        ),
    }
