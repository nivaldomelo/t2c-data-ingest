from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from t2c_ingest.api.router import api_router
from t2c_ingest.core.config import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(title=settings.app_name, version="0.1.0")

if settings.cors_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Liveness/readiness without auth or the /api/v1 prefix (Turn2C standard).
@app.get("/liveness")
def liveness() -> dict:
    return {"status": "ok", "app": settings.app_name}


@app.get("/readiness")
def readiness() -> dict:
    return {"status": "ok"}


app.include_router(api_router)
