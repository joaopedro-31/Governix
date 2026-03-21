from __future__ import annotations

import streamlit as st

from app.ui.eleitoral.helpers import is_municipal
from app.ui.eleitoral.queries import load_dependent_filters, load_tipos


def get_secret(key: str, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def init_session_state():
    default_uf = get_secret("UF_PADRAO", "CE")
    default_municipio = get_secret("MUNICIPIO_PADRAO", "FORTALEZA")

    tipos_default = load_tipos(default_uf)

    tipo_default = None
    for t in tipos_default:
        if "municipal" in t.lower():
            tipo_default = t
            break

    if not tipo_default:
        tipo_default = tipos_default[0] if tipos_default else None

    if tipo_default:
        anos_default, turnos_default, cargos_default, _, _ = load_dependent_filters(default_uf, tipo_default)
    else:
        anos_default, turnos_default, cargos_default = [], [], []

    if "filtros_aplicados" not in st.session_state:
        st.session_state["filtros_aplicados"] = {
            "uf": default_uf,
            "tipo": tipo_default,
            "ano": anos_default[0] if anos_default else None,
            "turno": turnos_default[0] if turnos_default else None,
            "cargo": "VEREADOR" if "VEREADOR" in cargos_default else (cargos_default[0] if cargos_default else None),
            "municipio": default_municipio if is_municipal(tipo_default) else "(Todos)",
            "regional": "(Todas)",
            "bairro": "(Todos)",
            "local_votacao": "(Todos)",
            "busca": "",
            "ordem_votos": "DESC",
            "mostrar_opcao": "10",
        }

    if "relatorio_candidato_nome" not in st.session_state:
        st.session_state["relatorio_candidato_nome"] = None

    if "relatorio_dados" not in st.session_state:
        st.session_state["relatorio_dados"] = None


def reset_secondary_filters_from_primary():
    f = st.session_state["filtros_aplicados"]

    default_municipio = get_secret("MUNICIPIO_PADRAO", "FORTALEZA")
    uf = f["uf"].strip().upper()
    tipo = f["tipo"]

    if tipo:
        anos, turnos, cargos, _, _ = load_dependent_filters(uf, tipo)
    else:
        anos, turnos, cargos = [], [], []

    f["ano"] = anos[0] if anos else None
    f["turno"] = turnos[0] if turnos else None
    f["cargo"] = "VEREADOR" if "VEREADOR" in cargos else (cargos[0] if cargos else None)

    if is_municipal(tipo):
        f["municipio"] = default_municipio
    else:
        f["municipio"] = "(Todos)"

    f["regional"] = "(Todas)"
    f["bairro"] = "(Todos)"
    f["local_votacao"] = "(Todos)"
    f["busca"] = ""

    st.session_state["relatorio_candidato_nome"] = None
    st.session_state["relatorio_dados"] = None