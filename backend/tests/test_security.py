"""Security-critical unit tests: crypto, log masking, SSRF guard, RBAC resolution."""
import pytest

from t2c_ingest.core.crypto import decrypt_secret, encrypt_secret
from t2c_ingest.core.log_masking import mask_secrets
from t2c_ingest.core import ssrf
from t2c_ingest.features.auth_bridge import permissions as perms


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
