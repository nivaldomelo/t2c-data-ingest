"""Executes library actions (install/uninstall/reinstall/check) as controlled subprocesses.

Security model: the command is ALWAYS an argv list (never a shell string), the package spec is
pre-validated against a strict whitelist, and pip runs against the worker's interpreter with a
timeout. stdout/stderr are captured into the action row; no secrets are involved.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from t2c_ingest.core.config import settings
from t2c_ingest.models.cluster_library import ClusterLibrary, ClusterLibraryAction


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _python_bin() -> str:
    return settings.library_pip_python or sys.executable


def build_command(action: str, package_spec: str, package_name: str) -> list[str]:
    """Build the safe argv for pip. `--user` targets the writable per-user site (non-root)."""
    py = _python_bin()
    base = [py, "-m", "pip"]
    if action in ("install", "reinstall"):
        cmd = base + ["install", "--no-input", "--disable-pip-version-check"]
        if settings.library_pip_user:
            cmd.append("--user")
        if action == "reinstall":
            cmd += ["--force-reinstall", "--upgrade"]
        cmd.append(package_spec)
        return cmd
    if action == "uninstall":
        return base + ["uninstall", "-y", package_name]
    # check
    return base + ["show", package_name]


def run_action(db: Session, action: ClusterLibraryAction) -> None:
    """Run a single action to completion, capturing logs and updating the library status."""
    library = db.get(ClusterLibrary, action.library_id) if action.library_id else None
    package_name = library.package_name if library else action.package_spec
    cmd = build_command(action.action, action.package_spec, package_name)

    action.status = "running"
    action.started_at = _now()
    action.command_safe = " ".join(cmd)
    if library:
        library.status = "installing" if action.action != "uninstall" else library.status
        library.last_action_at = action.started_at
        library.last_action_status = "running"
    _audit(db, f"CLUSTER_LIBRARY_{_verb(action.action)}_STARTED", action, library)
    db.commit()

    ok = False
    logs = ""
    error = None
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=settings.library_install_timeout,
        )
        logs = f"$ {' '.join(cmd)}\n\n[stdout]\n{proc.stdout}\n\n[stderr]\n{proc.stderr}"
        ok = proc.returncode == 0
        if not ok:
            error = (proc.stderr or proc.stdout or "pip retornou código de erro").strip()[:2000]
    except subprocess.TimeoutExpired:
        error = f"Tempo limite de {settings.library_install_timeout}s excedido."
        logs = f"$ {' '.join(cmd)}\n\n[erro] {error}"
    except Exception as exc:  # noqa: BLE001
        error = f"Falha ao executar: {exc}"
        logs = f"$ {' '.join(cmd)}\n\n[erro] {error}"

    action.finished_at = _now()
    action.duration_seconds = int((action.finished_at - action.started_at).total_seconds())
    action.status = "success" if ok else "failed"
    action.logs = logs[:200_000]
    action.error_message = error
    _finalize_library(library, action, ok)
    _audit(db, f"CLUSTER_LIBRARY_{_verb(action.action)}_{'SUCCEEDED' if ok else 'FAILED'}", action, library)
    db.commit()


def _finalize_library(library: ClusterLibrary | None, action: ClusterLibraryAction, ok: bool) -> None:
    if not library:
        return
    library.last_action_at = action.finished_at
    library.last_action_status = action.status
    library.last_action_message = action.error_message
    if action.action == "uninstall":
        if ok:
            library.status = "removed"
            library.active = False
            library.removed_at = action.finished_at
        else:
            library.status = "failed"
    else:  # install / reinstall
        if ok:
            library.status = "installed"
            library.active = True
            library.installed_at = action.finished_at
        else:
            library.status = "failed"


def _verb(action: str) -> str:
    return {"install": "INSTALL", "reinstall": "REINSTALL", "uninstall": "UNINSTALL", "check": "CHECK"}.get(
        action, "INSTALL"
    )


def _audit(db: Session, event: str, action: ClusterLibraryAction, library: ClusterLibrary | None) -> None:
    from t2c_ingest.models.audit import AuditEvent

    try:
        db.add(AuditEvent(
            action=event, entity_type="cluster_library",
            entity_id=str(library.id) if library else str(action.id),
            user_email=action.requested_by,
            detail={"package_spec": action.package_spec, "action": action.action,
                    "status": action.status, "action_id": action.id},
        ))
        db.flush()
    except Exception:  # noqa: BLE001
        db.rollback()
