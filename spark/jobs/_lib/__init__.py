"""Shared helpers baked into the Spark image, importable by jobs.

A job adds the jobs root to sys.path and imports from here, e.g.::

    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from _lib.t2c_s3 import build_s3_path, s3_client_from_env, s3_path_for_role
"""
