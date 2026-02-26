import os
import psycopg
import streamlit as st

def _get(k, default=None):
    return st.secrets.get(k, os.getenv(k, default))

def get_conn():
    conn = psycopg.connect(
        host=_get("PGHOST"),
        port=int(_get("PGPORT", 5432)),
        dbname=_get("PGDATABASE"),
        user=_get("PGUSER"),
        password=_get("PGPASSWORD"),
        sslmode=_get("PGSSLMODE", "require"),
    )
    schema = _get("PGSCHEMA", "public")
    with conn.cursor() as cur:
        cur.execute(f"SET search_path TO {schema}, public;")
    return conn