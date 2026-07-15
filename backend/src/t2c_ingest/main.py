from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from t2c_ingest.api.router import api_router
from t2c_ingest.core.bootstrap import enforce_secure_config
from t2c_ingest.core.config import is_dev_environment, settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fail fast on insecure production configuration (default JWT/encryption secrets, wildcard CORS
# with credentials). No-op in dev or when ALLOW_INSECURE_DEFAULTS is explicitly set.
enforce_secure_config()

_DEV = is_dev_environment(settings.env)

# Swagger/OpenAPI só em dev — em produção o schema da API não é exposto (PENTEST-04).
app = FastAPI(
    title=settings.app_name, version="0.1.0",
    docs_url="/docs" if _DEV else None,
    redoc_url="/redoc" if _DEV else None,
    openapi_url="/openapi.json" if _DEV else None,
)


@app.middleware("http")
async def _security_headers(request, call_next):
    """Headers de segurança em toda resposta (PENTEST-05)."""
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # frame-ancestors só (não restringe scripts) para não quebrar o Swagger em dev.
    resp.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
    resp.headers["Server"] = "t2c-data-ingest"  # não vaza a stack (uvicorn)
    if not _DEV:
        resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return resp

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


@app.middleware("http")
async def _capture_request_meta(request, call_next):
    """Record client IP + user-agent for audit trails (honors the reverse proxy's X-Real-IP)."""
    from t2c_ingest.core.request_ctx import set_request_meta

    xff = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for", "")
    ip = (xff.split(",")[0].strip() if xff else None) or (request.client.host if request.client else None)
    set_request_meta(ip, request.headers.get("user-agent"))
    return await call_next(request)


# Liveness/readiness without auth or the /api/v1 prefix (Turn2C standard).
@app.get("/liveness")
def liveness() -> dict:
    return {"status": "ok", "app": settings.app_name}


@app.get("/readiness")
def readiness() -> dict:
    return {"status": "ok"}


app.include_router(api_router)
