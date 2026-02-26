from sqlalchemy import create_engine
from app.core.config import settings

def build_readonly_engine():
    db_uri = (
        f"postgresql+psycopg://{settings.PGUSER}:{settings.PGPASSWORD}"
        f"@{settings.PGHOST}:{settings.PGPORT}/{settings.PGDATABASE}"
    )

    return create_engine(
        db_uri,
        pool_pre_ping=True,
        pool_recycle=300,
    )