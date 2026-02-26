import os
from dotenv import load_dotenv
import psycopg

load_dotenv()

PG_CONFIG = {
    "host": os.getenv("PGHOST"),
    "port": int(os.getenv("PGPORT")),
    "dbname": os.getenv("PGDATABASE"),
    "user": os.getenv("PGUSER"),
    "password": os.getenv("PGPASSWORD"),
    "sslmode": os.getenv("PGSSLMODE"),
}

DB_SCHEMA = os.getenv("PGSCHEMA", "public")  # se você usar 'geral', setar no .env

def get_conn():
    conn = psycopg.connect(**PG_CONFIG)
    # importante se seu schema padrão for 'geral'
    with conn.cursor() as cur:
        cur.execute(f"SET search_path TO {DB_SCHEMA}, public;")
    return conn