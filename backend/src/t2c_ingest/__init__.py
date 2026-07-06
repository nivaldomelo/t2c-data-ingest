"""T2C Data Ingest — operational layer for data ingestion, jobs, pipelines and executions.

Complementary product to t2c_data: reuses its Postgres and JWT authentication, but keeps
its own schema (``t2c_data_ingest``) and never duplicates users/roles/permissions.
"""

__version__ = "0.1.0"
