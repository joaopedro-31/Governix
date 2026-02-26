import re
from app.core.config import settings

DISALLOWED = re.compile(
    r"\b(insert|update|delete|alter|drop|truncate|create|grant|revoke|copy|call|execute)\b",
    re.IGNORECASE,
)

def _normalize(sql: str) -> str:
    return sql.strip().strip("`")

def _ensure_select_only(sql: str) -> None:
    s = sql.lstrip().lower()
    if not s.startswith("select"):
        raise ValueError("Only SELECT is allowed")
    if ";" in sql:
        raise ValueError("Semicolons not allowed")
    if DISALLOWED.search(sql):
        raise ValueError("Dangerous keyword detected")

def _enforce_limit(sql: str) -> str:
    m = re.search(r"\blimit\s+(\d+)\b", sql, flags=re.IGNORECASE)
    if m:
        current = int(m.group(1))
        if current > settings.AI_MAX_ROWS:
            sql = re.sub(r"\blimit\s+\d+\b", f"LIMIT {settings.AI_MAX_ROWS}", sql, flags=re.IGNORECASE)
        return sql
    return f"{sql}\nLIMIT {settings.AI_MAX_ROWS}"

def validate_queries(queries: list[str]) -> list[str]:
    safe = []
    for q in queries:
        q = _normalize(q)
        _ensure_select_only(q)
        q = _enforce_limit(q)
        safe.append(q)
    return safe
