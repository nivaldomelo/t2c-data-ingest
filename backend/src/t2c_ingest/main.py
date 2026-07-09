from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from t2c_ingest.api.router import api_router
from t2c_ingest.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fail fast on insecure production configuration (default JWT/encryption secrets, wildcard CORS
# with credentials). No-op in dev or when ALLOW_INSECURE_DEFAULTS is explicitly set.
_security_errors = settings.security_errors()
if _security_errors:
    raise RuntimeError(
        "Configuração de segurança inválida para produção:\n  - "
        + "\n  - ".join(_security_errors)
        + "\nCorrija as variáveis de ambiente ou defina ALLOW_INSECURE_DEFAULTS=true (apenas dev)."
    )

app = FastAPI(title=settings.app_name, version="0.1.0")

# Never combine credentialed CORS with a wildcard origin.
_origins = [o for o in settings.cors_origins_list if o != "*"]
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
elif settings.cors_origins_list:
    logger.warning("CORS_ALLOW_ORIGINS='*' ignorado: incompatível com credenciais.")


# Liveness/readiness without auth or the /api/v1 prefix (Turn2C standard).
@app.get("/liveness")
def liveness() -> dict:
    return {"status": "ok", "app": settings.app_name}


@app.get("/readiness")
def readiness() -> dict:
    return {"status": "ok"}


app.include_router(api_router)
