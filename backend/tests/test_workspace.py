"""Path-traversal and read-guard tests for the code workspace."""
import os

import pytest

from t2c_ingest.features.jobs import workspace_service as ws


def test_safe_path_rejects_traversal(tmp_path):
    root = str(tmp_path)
    # absolute path rejected
    with pytest.raises(ws.WorkspaceError):
        ws.safe_path(root, "/etc/passwd")
    # parent traversal rejected
    with pytest.raises(ws.WorkspaceError):
        ws.safe_path(root, "../../etc/passwd")
    # windows-style absolute rejected
    with pytest.raises(ws.WorkspaceError):
        ws.safe_path(root, "C:\\secrets")


def test_check_readable_blocks_secrets():
    for blocked in ("/x/.env", "/x/id_rsa.pem", "/x/service.key", "/x/.hidden"):
        with pytest.raises(ws.WorkspaceError):
            ws.check_readable(blocked)
    # normal source is fine
    ws.check_readable("/x/main.py")
    ws.check_readable("/x/query.sql")
