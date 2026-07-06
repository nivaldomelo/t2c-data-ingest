from fastapi import APIRouter

from t2c_ingest.features.airflow_migration.router import router as airflow_router
from t2c_ingest.features.auth.router import router as auth_router
from t2c_ingest.features.clusters.router import router as clusters_router
from t2c_ingest.features.dashboard.router import router as dashboard_router
from t2c_ingest.features.executions.router import router as executions_router
from t2c_ingest.features.jobs.router import router as jobs_router
from t2c_ingest.features.pipelines.router import router as pipelines_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(clusters_router)
api_router.include_router(jobs_router)
api_router.include_router(pipelines_router)
api_router.include_router(executions_router)
api_router.include_router(airflow_router)
