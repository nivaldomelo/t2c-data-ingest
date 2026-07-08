from fastapi import APIRouter

from t2c_ingest.features.airflow_migration.router import router as airflow_router
from t2c_ingest.features.auth.router import router as auth_router
from t2c_ingest.features.cluster_libraries.router import router as libraries_router
from t2c_ingest.features.cluster_libraries.router import actions_router as library_actions_router
from t2c_ingest.features.clusters.router import router as clusters_router
from t2c_ingest.features.connections.router import router as connections_router
from t2c_ingest.features.dashboard.router import router as dashboard_router
from t2c_ingest.features.executions.router import router as executions_router
from t2c_ingest.features.ingestion_control.router import router as ingestion_control_router
from t2c_ingest.features.variables.router import router as variables_router
from t2c_ingest.features.jobs.router import router as jobs_router
from t2c_ingest.features.jobs.workspace_router import router as jobs_workspace_router
from t2c_ingest.features.pipelines.router import router as pipelines_router
from t2c_ingest.features.pipelines.router import pe_router as pipeline_executions_router
from t2c_ingest.features.schedules.router import router as schedules_router
from t2c_ingest.features.tags.router import router as tags_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(clusters_router)
api_router.include_router(connections_router)
api_router.include_router(jobs_router)
api_router.include_router(jobs_workspace_router)
api_router.include_router(pipelines_router)
api_router.include_router(pipeline_executions_router)
api_router.include_router(schedules_router)
api_router.include_router(executions_router)
api_router.include_router(ingestion_control_router)
api_router.include_router(variables_router)
api_router.include_router(tags_router)
api_router.include_router(libraries_router)
api_router.include_router(library_actions_router)
api_router.include_router(airflow_router)
