"""Shared security bootstrap: fail fast on insecure production configuration.

Called by every process entrypoint (API, worker, scheduler) so none of them can start with
default/weak secrets or a wildcard credentialed CORS outside dev. The worker in particular
decrypts every connection secret, so it must be guarded too — not only the API.
"""
from __future__ import annotations

from t2c_ingest.core.config import settings


def enforce_secure_config() -> None:
    errors = settings.security_errors()
    if errors:
        raise RuntimeError(
            "Configuração de segurança inválida para produção:\n  - "
            + "\n  - ".join(errors)
            + "\nCorrija as variáveis de ambiente ou defina ALLOW_INSECURE_DEFAULTS=true (apenas dev)."
        )
