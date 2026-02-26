import os
import psycopg
import streamlit as st

def _get(key: str, default=None):
    # Streamlit Cloud: st.secrets; Local: os.getenv
    if hasattr(st, "secrets") and key in st.secrets:
        return st.secrets[key]
    return os.getenv(key, default)

def get_conn():
    cfg = {
        "host": _get("PGHOST"),
        "port": int(_get("PGPORT", 5432)),
        "dbname": _get("PGDATABASE"),
        "user": _get("PGUSER"),
        "password": _get("PGPASSWORD"),
        "sslmode": _get("PGSSLMODE", "require"),
    }

    schema = _get("PGSCHEMA", "public")

    conn = psycopg.connect(**cfg)
    # garante schema (se você usa 'geral', isso evita "relation does not exist")
    with conn.cursor() as cur:
        cur.execute(f"SET search_path TO {schema}, public;")
    return conn