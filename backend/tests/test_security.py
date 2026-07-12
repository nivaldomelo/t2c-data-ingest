"""Security-critical unit tests: crypto, log masking, SSRF guard, RBAC resolution."""
from types import SimpleNamespace

import pytest

from t2c_ingest.core.crypto import decrypt_secret, encrypt_secret
from t2c_ingest.core.log_masking import mask_secrets
from t2c_ingest.core import ssrf
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.connections import s3_service
from t2c_ingest.features.connections.worker_support import _inject_s3, ResolvedConnections


def test_crypto_roundtrip():
    token = encrypt_secret("s3nha-super-secreta")
    assert token != "s3nha-super-secreta"
    assert decrypt_secret(token) == "s3nha-super-secreta"
    assert decrypt_secret(None) == ""


def test_mask_secrets_patterns():
    assert "***" in mask_secrets("password=hunter2 ok") and "hunter2" not in mask_secrets("password=hunter2 ok")
    assert "MyP4ss" not in mask_secrets("postgresql://user:MyP4ss@host/db")
    assert "abc.def" not in mask_secrets("Authorization: Bearer abc.def.ghi")
    assert mask_secrets("valor cru X9y8z7w6", ["X9y8z7w6"]).count("***") == 1


def test_mask_secrets_aws_keys():
    # AWS_* env vars (leading '_' defeats the generic \b rule -> dedicated AWS pattern)
    assert "AKIAEXAMPLE123" not in mask_secrets("AWS_ACCESS_KEY_ID=AKIAEXAMPLE123")
    assert "topsecret/val+" not in mask_secrets("AWS_SECRET_ACCESS_KEY=topsecret/val+")
    assert "FQoGZlong" not in mask_secrets("AWS_SESSION_TOKEN=FQoGZlong")
    # spark hadoop s3a confs use '.' separators
    masked = mask_secrets("--conf spark.hadoop.fs.s3a.secret.key=abc123secret")
    assert "abc123secret" not in masked and "***" in masked
    # exact decrypted values are still redacted regardless of shape
    assert "rawS3Secret9" not in mask_secrets("... rawS3Secret9 ...", ["rawS3Secret9"])


def test_s3_sanitize_prefix_blocks_traversal():
    assert s3_service.sanitize_prefix("bronze/vendas") == "bronze/vendas"
    assert s3_service.sanitize_prefix(None) == ""
    for bad in ("../etc", "a/../b", "/absolute", "s3://bucket/x", "\\windows"):
        with pytest.raises(ValueError):
            s3_service.sanitize_prefix(bad)


def _fake_s3_conn(auth_mode="access_key", *, with_keys=True, endpoint="http://minio:9000"):
    return SimpleNamespace(
        name="datalake_test",
        connection_type="s3",
        active=True,
        extra_params={
            "aws_region": "us-east-1",
            "bucket_name": "t2c-lake",
            "base_prefix": "bronze",
            "default_layer": "bronze",
            "auth_mode": auth_mode,
            "endpoint_url": endpoint,
            "ssl_enabled": False,
        },
        aws_access_key_id_encrypted=encrypt_secret("AKIATESTKEY") if with_keys else None,
        aws_secret_access_key_encrypted=encrypt_secret("shh-secret-val") if with_keys else None,
        aws_session_token_encrypted=None,
    )


def test_worker_inject_s3_env_and_confs_no_secret_leak():
    result = ResolvedConnections()
    _inject_s3(result, "TARGET_", _fake_s3_conn(), test=False)
    # role-prefixed non-secret env
    assert result.env["TARGET_TYPE"] == "s3"
    assert result.env["TARGET_S3_BUCKET"] == "t2c-lake"
    assert result.env["TARGET_S3_REGION"] == "us-east-1"
    # standard AWS creds via env (for boto3 + S3A default chain)
    assert result.env["AWS_ACCESS_KEY_ID"] == "AKIATESTKEY"
    assert result.env["AWS_SECRET_ACCESS_KEY"] == "shh-secret-val"
    # secrets tracked for masking, and NOT present in the human-safe notes or in --conf
    assert "AKIATESTKEY" in result.secret_values and "shh-secret-val" in result.secret_values
    joined_confs = " ".join(result.spark_confs)
    joined_notes = " ".join(result.notes)
    assert "shh-secret-val" not in joined_confs and "shh-secret-val" not in joined_notes
    assert "AKIATESTKEY" not in joined_confs and "AKIATESTKEY" not in joined_notes
    # non-secret s3a confs present (endpoint/path-style/ssl/region)
    assert any("fs.s3a.endpoint=http://minio:9000" in c for c in result.spark_confs)
    assert any("fs.s3a.path.style.access=true" in c for c in result.spark_confs)
    assert any("fs.s3a.connection.ssl.enabled=false" in c for c in result.spark_confs)


def test_worker_inject_s3_instance_profile_no_keys():
    result = ResolvedConnections()
    _inject_s3(result, "SOURCE_", _fake_s3_conn(auth_mode="instance_profile", with_keys=False), test=False)
    # no static credentials injected — rely on the instance/pod profile chain
    assert "AWS_ACCESS_KEY_ID" not in result.env
    assert result.secret_values == []
    assert result.env["SOURCE_S3_BUCKET"] == "t2c-lake"


@pytest.mark.parametrize("ip,internal", [
    ("127.0.0.1", True), ("10.1.2.3", True), ("192.168.0.5", True), ("169.254.169.254", True),
    ("::1", True), ("::ffff:169.254.169.254", True), ("2002:a9fe:a9fe::", True),
    ("0.0.0.0", True), ("8.8.8.8", False), ("1.1.1.1", False),
])
def test_ip_is_internal(ip, internal):
    assert ssrf._ip_is_internal(ip) is internal


def test_assert_public_http_url_rejects():
    with pytest.raises(ValueError):
        ssrf.assert_public_http_url("ftp://example.com")     # scheme
    with pytest.raises(ValueError):
        ssrf.assert_public_http_url("http://127.0.0.1/hook")  # loopback
    with pytest.raises(ValueError):
        ssrf.assert_public_http_url("http://169.254.169.254/latest/")  # metadata


def test_rbac_resolution():
    admin = perms.resolve_ingest_permissions({"admin"}, has_access=False)
    assert admin == set(perms.ALL_PERMISSIONS)
    viewer = perms.resolve_ingest_permissions({"viewer"}, has_access=True)
    assert viewer == set(perms.READ_ONLY_PERMISSIONS)
    assert perms.resolve_ingest_permissions({"viewer"}, has_access=False) == set()
    # read-only must never include admin, secret-read or raw code read
    assert perms.INGEST_ADMIN not in viewer
    assert perms.INGEST_VARIABLES_SECRET_READ not in viewer
    assert perms.INGEST_JOBS_CODE_READ not in viewer
    # and never a mutating permission
    for p in (perms.INGEST_RUN, perms.INGEST_JOBS_CREATE, perms.INGEST_CONNECTIONS_WRITE,
              perms.INGEST_RUNTIME_BUILD, perms.INGEST_ALERTS_MANAGE):
        assert p not in viewer


def test_data_lake_sql_guard_allows_reads():
    from t2c_ingest.features.data_lake import sql_guard as g
    for ok in ("SELECT * FROM bronze.clientes", "with x as (select 1) select * from x",
               "SHOW TABLES", "DESCRIBE bronze.clientes", "EXPLAIN SELECT 1"):
        assert g.validate_read_only(ok)


def test_data_lake_sql_guard_blocks_writes_and_multi():
    from t2c_ingest.features.data_lake import sql_guard as g
    for bad in ("DROP TABLE x", "INSERT INTO x VALUES (1)", "UPDATE x SET a=1", "DELETE FROM x",
                "MERGE INTO x", "ALTER TABLE x", "CREATE TABLE x AS SELECT 1", "TRUNCATE TABLE x",
                "SET spark.foo=1", "MSCK REPAIR TABLE x", "REFRESH TABLE x", "ADD JAR x",
                "CACHE TABLE x", "SELECT 1; DROP TABLE x", ""):
        with pytest.raises(g.SqlGuardError):
            g.validate_read_only(bad)


def test_data_lake_sql_guard_limit_and_translate():
    from t2c_ingest.features.data_lake import sql_guard as g
    # LIMIT applied when absent; capped to MAX when too big; not appended to SHOW.
    assert g.apply_limit("SELECT * FROM t", None) == ("SELECT * FROM t LIMIT 100", 100)
    assert g.apply_limit("SELECT * FROM t LIMIT 99999", None) == ("SELECT * FROM t LIMIT 1000", 1000)
    assert g.apply_limit("SELECT * FROM t", 50) == ("SELECT * FROM t LIMIT 50", 50)
    assert g.apply_limit("SHOW TABLES", None)[0] == "SHOW TABLES"
    # Logical name translated only when the view is known.
    assert g.translate_logical_names("SELECT * FROM bronze.clientes", {"bronze__clientes"}) == \
        "SELECT * FROM bronze__clientes"
    assert g.translate_logical_names("SELECT * FROM other.tbl", {"bronze__clientes"}) == \
        "SELECT * FROM other.tbl"


def test_data_lake_catalog_config():
    from types import SimpleNamespace
    from t2c_ingest.features.data_lake.catalog_config import resolve_catalog_config
    disabled = resolve_catalog_config(SimpleNamespace(extra_params={}))
    assert disabled.enabled is False
    layered = resolve_catalog_config(SimpleNamespace(extra_params={
        "catalog_enabled": True, "catalog_mode": "layer_as_schema",
        "layers": [{"name": "bronze", "bucket": "b-bronze", "base_prefix": "datalake"}],
    }))
    assert layered.enabled and layered.mode == "layer_as_schema"
    assert layered.layers[0].name == "bronze" and layered.layers[0].bucket == "b-bronze"
    prefixed = resolve_catalog_config(SimpleNamespace(extra_params={
        "catalog_enabled": True, "catalog_mode": "prefix_as_schema",
        "bucket_name": "lake", "base_prefix": "/datalake/",
    }))
    assert prefixed.mode == "prefix_as_schema" and prefixed.root.base_prefix == "datalake"


def test_rbac_s3_permissions():
    admin = perms.resolve_ingest_permissions({"admin"}, has_access=False)
    viewer = perms.resolve_ingest_permissions({"viewer"}, has_access=True)
    # S3 read + list are read-only friendly; write is admin-only (mutating).
    for p in (perms.INGEST_S3_READ, perms.INGEST_S3_LIST, perms.INGEST_S3_WRITE):
        assert p in admin
    assert perms.INGEST_S3_READ in viewer
    assert perms.INGEST_S3_LIST in viewer
    assert perms.INGEST_S3_WRITE not in viewer
