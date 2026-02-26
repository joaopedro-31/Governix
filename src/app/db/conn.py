# src/app/db/conn.py
import os
from pathlib import Path
import psycopg

def _load_dotenv_if_exists():
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    root = Path(__file__).resolve().parents[3]  # raiz do projeto
    env_path = root / ".env"
    if env_path.exists():
        load_dotenv(env_path)

def _get_secret_safe(key: str, default=None):
    """
    Tenta ler de st.secrets (Streamlit Cloud) sem quebrar se não existir.
    Cai para os.getenv (Render/localhost).
    """
    # Render/localhost: variáveis de ambiente
    env_val = os.getenv(key, default)

    # Streamlit Cloud: secrets (pode não existir em Render)
    try:
        import streamlit as st
        try:
            # st.secrets pode lançar StreamlitSecretNotFoundError se não houver secrets.toml
            return st.secrets.get(key, env_val)
        except Exception:
            return env_val
    except Exception:
        return env_val

def get_conn():
    _load_dotenv_if_exists()

    cfg = {
        "host": _get_secret_safe("PGHOST"),
        "port": int(_get_secret_safe("PGPORT", 5432)),
        "dbname": _get_secret_safe("PGDATABASE"),
        "user": _get_secret_safe("PGUSER"),
        "password": _get_secret_safe("PGPASSWORD"),
        "sslmode": _get_secret_safe("PGSSLMODE", "require"),
    }

    schema = _get_secret_safe("PGSCHEMA", "public")

    conn = psycopg.connect(**cfg)
    with conn.cursor() as cur:
        cur.execute(f"SET search_path TO {schema}, public;")
    return conn