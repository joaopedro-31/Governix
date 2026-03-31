from __future__ import annotations


def format_int(value) -> str:
    try:
        return f"{int(value):,}".replace(",", ".")
    except Exception:
        return "-"


def normalize_tipo(tipo: str | None) -> str:
    return (tipo or "").strip().upper()


def is_municipal(tipo: str | None) -> bool:
    t = normalize_tipo(tipo)
    return "MUNICIP" in t


def is_estadual(tipo: str | None) -> bool:
    t = normalize_tipo(tipo)
    return "ESTAD" in t


def first_or(default, values):
    return default if default in values else (values[0] if values else None)