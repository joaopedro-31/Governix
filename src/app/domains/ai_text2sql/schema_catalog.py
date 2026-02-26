from sqlalchemy import inspect
from sqlalchemy.engine import Engine

ALLOWED_TABLES = [
    "dim_eleicao",
    "dim_municipio",
    "dim_regional",
    "dim_bairro",
    "dim_local_votacao",
    "dim_partido",
    "dim_candidato",
    "fato_votos_local",
]

def build_allowed_schema(engine: Engine) -> str:
    insp = inspect(engine)
    lines: list[str] = []
    for t in ALLOWED_TABLES:
        cols = insp.get_columns(t)
        col_names = ", ".join(c["name"] for c in cols)
        lines.append(f"- {t}({col_names})")
    return "\n".join(lines)
