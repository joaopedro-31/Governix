# src/app/ui/dashboard.py
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# =========================
# Import robusto (local + cloud)
# =========================
SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app.db.conn import get_conn  # noqa: E402

# =========================
# Streamlit config + CSS
# =========================
st.set_page_config(
    page_title="GOVERNIX • Eleições",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
.block-container {
  padding-top: 0.8rem;
  padding-bottom: 1rem;
  padding-left: 0.8rem;
  padding-right: 0.8rem;
}

@media (max-width: 768px) {
  h1 { font-size: 1.25rem; }
  h2, h3 { font-size: 1.05rem; }
  .block-container { padding-left: 0.6rem; padding-right: 0.6rem; }
  div.stButton > button { width: 100%; }
  .stTextInput input { min-height: 44px; }
  div[data-baseweb="select"] { min-height: 44px; }
}
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Helpers
# =========================
def df_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                cols = [d.name for d in cur.description]
                rows = cur.fetchall()
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        st.error(f"Erro SQL: {e}")
        st.code(sql)
        st.write(params)
        raise


def get_secret(key: str, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def build_where_and_params(base_params: dict, busca: str | None = None, candidato: str | None = None):
    where = [
        "ano = %(ano)s",
        "tipo = %(tipo)s",
        "turno = %(turno)s",
        "cargo = %(cargo)s",
        "uf = %(uf)s",
    ]

    sql_params = {
        "ano": base_params["ano"],
        "tipo": base_params["tipo"],
        "turno": base_params["turno"],
        "cargo": base_params["cargo"],
        "uf": base_params["uf"],
    }

    if base_params.get("municipio"):
        where.append("municipio = %(municipio)s")
        sql_params["municipio"] = base_params["municipio"]

    if base_params.get("regional"):
        where.append("regional = %(regional)s")
        sql_params["regional"] = base_params["regional"]

    if base_params.get("bairro"):
        where.append("bairro = %(bairro)s")
        sql_params["bairro"] = base_params["bairro"]

    if base_params.get("local_votacao"):
        where.append("local_votacao = %(local_votacao)s")
        sql_params["local_votacao"] = base_params["local_votacao"]

    if busca and busca.strip():
        where.append("candidato ILIKE %(busca)s")
        sql_params["busca"] = f"%{busca.strip()}%"

    if candidato:
        where.append("candidato = %(candidato)s")
        sql_params["candidato"] = candidato

    return where, sql_params


# =========================
# Carregamento de filtros
# =========================
@st.cache_data(ttl=300)
def load_filters(uf: str):
    anos = df_query(
        """
        SELECT DISTINCT ano
        FROM mv_ranking_candidato
        ORDER BY ano DESC;
        """
    )["ano"].tolist()

    tipos = df_query(
        """
        SELECT DISTINCT tipo
        FROM mv_ranking_candidato
        ORDER BY tipo;
        """
    )["tipo"].tolist()

    turnos = df_query(
        """
        SELECT DISTINCT turno
        FROM mv_ranking_candidato
        ORDER BY turno;
        """
    )["turno"].tolist()

    cargos = df_query(
        """
        SELECT DISTINCT cargo
        FROM mv_ranking_candidato
        ORDER BY cargo;
        """
    )["cargo"].tolist()

    municipios = df_query(
        """
        SELECT DISTINCT municipio
        FROM mv_ranking_candidato
        WHERE uf = %(uf)s
        ORDER BY municipio;
        """,
        {"uf": uf},
    )["municipio"].tolist()

    regionais = df_query(
        """
        SELECT DISTINCT regional
        FROM mv_ranking_candidato
        WHERE uf = %(uf)s
          AND regional <> ''
        ORDER BY regional;
        """,
        {"uf": uf},
    )["regional"].tolist()

    return anos, tipos, turnos, cargos, municipios, regionais


@st.cache_data(ttl=300)
def load_bairros_locais(uf: str, municipio: str | None):
    if not municipio:
        return [], []

    bairros_df = df_query(
        """
        SELECT DISTINCT bairro
        FROM mv_ranking_candidato
        WHERE uf = %(uf)s
          AND municipio = %(municipio)s
          AND bairro <> ''
        ORDER BY bairro;
        """,
        {"uf": uf, "municipio": municipio},
    )

    locais_df = df_query(
        """
        SELECT DISTINCT local_votacao
        FROM mv_ranking_candidato
        WHERE uf = %(uf)s
          AND municipio = %(municipio)s
          AND local_votacao <> ''
        ORDER BY local_votacao;
        """,
        {"uf": uf, "municipio": municipio},
    )

    bairros = bairros_df["bairro"].tolist() if len(bairros_df) else []
    locais = locais_df["local_votacao"].tolist() if len(locais_df) else []
    return bairros, locais


# =========================
# Consultas principais
# =========================
@st.cache_data(ttl=60)
def query_ranking(params: dict, order_by_votes: bool, top_n: int | None, busca: str | None = None) -> pd.DataFrame:
    where, sql_params = build_where_and_params(params, busca=busca)

    order_sql = "ORDER BY votos DESC, candidato ASC" if order_by_votes else "ORDER BY candidato ASC"

    limit_sql = ""
    if top_n is not None:
        limit_sql = "LIMIT %(limite)s"
        sql_params["limite"] = top_n

    sql = f"""
    SELECT
        candidato,
        partido,
        SUM(votos) AS votos
    FROM mv_ranking_candidato
    WHERE {' AND '.join(where)}
    GROUP BY candidato, partido
    {order_sql}
    {limit_sql};
    """

    return df_query(sql, sql_params)


@st.cache_data(ttl=60)
def list_candidatos_match(params: dict, termo: str) -> list[str]:
    where, sql_params = build_where_and_params(params, busca=termo)

    sql = f"""
    SELECT DISTINCT candidato
    FROM mv_ranking_candidato
    WHERE {' AND '.join(where)}
    ORDER BY candidato;
    """

    df = df_query(sql, sql_params)
    return df["candidato"].tolist() if len(df) else []


@st.cache_data(ttl=60)
def query_relatorio_candidato(params: dict, candidato: str) -> dict:
    # relatório do candidato ignora bairro e local para não "cortar" o total
    params_rel = dict(params)
    params_rel["bairro"] = None
    params_rel["local_votacao"] = None

    where, sql_params = build_where_and_params(params_rel, candidato=candidato)

    sql_total = f"""
    SELECT
        candidato,
        partido,
        municipio,
        ano,
        tipo,
        turno,
        cargo,
        SUM(votos) AS votos_totais
    FROM mv_ranking_candidato
    WHERE {' AND '.join(where)}
    GROUP BY candidato, partido, municipio, ano, tipo, turno, cargo;
    """
    info = df_query(sql_total, sql_params)
    if not len(info):
        return {"ok": False}

    sql_bairros = f"""
    SELECT
        CASE
            WHEN bairro IS NULL OR bairro = '' THEN '(Sem bairro)'
            ELSE bairro
        END AS bairro,
        SUM(votos) AS votos
    FROM mv_ranking_candidato
    WHERE {' AND '.join(where)}
    GROUP BY 1
    ORDER BY votos DESC
    LIMIT 10;
    """
    top_bairros = df_query(sql_bairros, sql_params)

    sql_locais = f"""
    SELECT
        local_votacao,
        SUM(votos) AS votos
    FROM mv_ranking_candidato
    WHERE {' AND '.join(where)}
    GROUP BY 1
    ORDER BY votos DESC
    LIMIT 10;
    """
    top_locais = df_query(sql_locais, sql_params)

    sql_regionais = f"""
    SELECT
        CASE
            WHEN regional IS NULL OR regional = '' THEN '(Sem regional)'
            ELSE regional
        END AS regional,
        SUM(votos) AS votos
    FROM mv_ranking_candidato
    WHERE {' AND '.join(where)}
    GROUP BY 1
    ORDER BY votos DESC
    LIMIT 3;
    """
    top_regionais = df_query(sql_regionais, sql_params)

    return {
        "ok": True,
        "info": info.iloc[0].to_dict(),
        "top_bairros": top_bairros,
        "top_locais": top_locais,
        "top_regionais": top_regionais,
    }


# =========================
# UI
# =========================
st.title("GOVERNIX • Dashboard Eleitoral")

with st.expander("Diagnóstico", expanded=False):
    try:
        with get_conn() as c:
            with c.cursor() as cur:
                cur.execute("SELECT current_schema(), now();")
                schema, now = cur.fetchone()
                st.success(f"DB OK • schema={schema} • now={now}")
                cur.execute("SELECT 1 FROM mv_ranking_candidato LIMIT 1;")
                st.success("Materialized view mv_ranking_candidato OK")
    except Exception as e:
        st.error("Falha ao conectar ou consultar a materialized view.")
        st.exception(e)
        st.stop()

default_uf = get_secret("UF_PADRAO", "CE")

st.subheader("Filtros")

# Linha 1: UF / Município
c1, c2 = st.columns(2)
with c1:
    uf = st.text_input("UF", value=default_uf).strip().upper()

anos, tipos, turnos, cargos, municipios, regionais = load_filters(uf)

with c2:
    mun_options = ["(Todos)"] + municipios if municipios else ["(Todos)"]
    fortaleza_idx = 0
    for i, m in enumerate(mun_options):
        if isinstance(m, str) and m.strip().upper() == "FORTALEZA":
            fortaleza_idx = i
            break
    municipio = st.selectbox("Município", mun_options, index=fortaleza_idx)

municipio_val = None if municipio == "(Todos)" else municipio
bairros, locais = load_bairros_locais(uf, municipio_val)

# Linha 2: Tipo / Ano
c3, c4 = st.columns(2)
with c3:
    tipo = st.selectbox("Tipo", tipos) if tipos else ""
with c4:
    ano = st.selectbox("Ano", anos) if anos else 0

# Linha 3: Turno / Cargo
c5, c6 = st.columns(2)
with c5:
    turno = st.selectbox("Turno", turnos) if turnos else 1
with c6:
    cargo_default_idx = cargos.index("VEREADOR") if "VEREADOR" in cargos else 0
    cargo = st.selectbox("Cargo", cargos, index=cargo_default_idx) if cargos else ""

# Linha 4: Regional / Bairro
c7, c8 = st.columns(2)
with c7:
    regional = st.selectbox("Regional (opcional)", ["(Todas)"] + regionais) if regionais else "(Todas)"
with c8:
    if municipio_val is None:
        bairro = "(Todos)"
        st.selectbox("Bairro (opcional)", ["(Todos)"], index=0, disabled=True)
    else:
        bairro = st.selectbox("Bairro (opcional)", ["(Todos)"] + bairros) if bairros else "(Todos)"

# Linha 5: Local / Busca
c9, c10 = st.columns(2)
with c9:
    if municipio_val is None:
        local_votacao = "(Todos)"
        st.selectbox("Local de votação (opcional)", ["(Todos)"], index=0, disabled=True)
    else:
        local_votacao = st.selectbox("Local de votação (opcional)", ["(Todos)"] + locais) if locais else "(Todos)"
with c10:
    busca = st.text_input("Buscar candidato (contém)")

# Linha 6: Ordenação / Quantidade
c11, c12 = st.columns(2)
with c11:
    ordem = st.selectbox("Ordenação", ["Alfabética", "Votos (desc)"])
with c12:
    mostrar_opcao = st.selectbox("Mostrar quantos?", ["10", "50", "100", "200", "500", "Todos"], index=0)
    top_n = None if mostrar_opcao == "Todos" else int(mostrar_opcao)

params = {
    "ano": ano,
    "tipo": tipo,
    "turno": turno,
    "cargo": cargo,
    "uf": uf,
    "municipio": municipio_val,
    "regional": None if regional == "(Todas)" else regional,
    "bairro": None if bairro == "(Todos)" else bairro,
    "local_votacao": None if local_votacao == "(Todos)" else local_votacao,
}

# ====== Relatório (se houver busca) ======
if busca and len(busca.strip()) >= 2:
    candidatos_match = list_candidatos_match(params, busca.strip())

    if len(candidatos_match) == 0:
        st.warning("Nenhum candidato encontrado para essa busca no recorte atual.")
    else:
        st.subheader("Relatório do candidato")
        cand_sel = st.selectbox("Selecione o candidato", candidatos_match, index=0)

        if st.button("Gerar relatório", type="primary"):
            rel = query_relatorio_candidato(params, cand_sel)

            if not rel.get("ok"):
                st.warning("Sem dados para esse candidato no recorte atual.")
            else:
                info = rel["info"]
                cA, cB, cC, cD = st.columns(4)
                cA.metric("Votos totais", f"{int(info['votos_totais']):,}".replace(",", "."))
                cB.metric("Partido", info["partido"])
                cC.metric("Município", info["municipio"])
                cD.metric("Eleição", f"{info['ano']} • {info['tipo']} • T{info['turno']}")

                st.markdown(f"**Candidato:** {info['candidato']}  \n**Cargo:** {info['cargo']}")

                t1, t2 = st.columns(2)
                with t1:
                    st.markdown("### Top 10 Bairros")
                    st.dataframe(rel["top_bairros"], use_container_width=True, hide_index=True)
                with t2:
                    st.markdown("### Top 10 Locais de votação")
                    st.dataframe(rel["top_locais"], use_container_width=True, hide_index=True)

                st.markdown("### Top 3 Regionais")
                st.dataframe(rel["top_regionais"], use_container_width=True, hide_index=True)

# ====== Tabela ======
st.subheader("Candidatos")

df = query_ranking(
    params=params,
    order_by_votes=(ordem == "Votos (desc)"),
    top_n=top_n,
    busca=busca,
)

st.dataframe(df, use_container_width=True, hide_index=True, height=520)