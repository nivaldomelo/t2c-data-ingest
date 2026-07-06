"""Auth bridge: reuse t2c_data authentication/authorization without duplicating users.

The ingest product validates the same JWT (shared secret) and READS users/roles/permissions
from the t2c_data schema. It defines its own ingest permissions, derived from the existing
role names — no new user or role tables are created here.
"""
