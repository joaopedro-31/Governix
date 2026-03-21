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

.metric-card {
  background: #111827;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 12px;
  padding: 12px 14px;
}

.small-muted {
  color: #9ca3af;
  font-size: 0.88rem;
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
                if cur.description is None:
                    return pd.DataFrame()
                cols = [d.name for d in cur.description]
                rows = cur.fetchall()
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        st.error(f"Erro SQL: {e}")
        raise


def get_secret(key: str, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def format_int(value) -> str:
    try:
        return f"{int(value):,}".replace(",", ".")
    except Exception:
        return "-"


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
    # ignora bairro e local para não cortar o total do município no relatório
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
# Session state
# =========================
default_uf = get_secret("UF_PADRAO", "CE")
default_municipio = get_secret("MUNICIPIO_PADRAO", "FORTALEZA")

if "filtros_aplicados" not in st.session_state:
    st.session_state["filtros_aplicados"] = {
        "uf": default_uf,
        "municipio": default_municipio,
        "tipo": None,
        "ano": None,
        "turno": None,
        "cargo": None,
        "regional": "(Todas)",
        "bairro": "(Todos)",
        "local_votacao": "(Todos)",
        "busca": "",
        "ordem": "Votos (desc)",
        "mostrar_opcao": "10",
    }

if "relatorio_candidato_nome" not in st.session_state:
    st.session_state["relatorio_candidato_nome"] = None

if "relatorio_dados" not in st.session_state:
    st.session_state["relatorio_dados"] = None


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

# usa UF do estado aplicado, não do widget em tempo real
uf_for_filters = st.session_state["filtros_aplicados"]["uf"].strip().upper()
anos, tipos, turnos, cargos, municipios, regionais = load_filters(uf_for_filters)

municipio_val_for_filters = st.session_state["filtros_aplicados"]["municipio"]
if municipio_val_for_filters == "(Todos)":
    municipio_val_for_filters = None

bairros, locais = load_bairros_locais(uf_for_filters, municipio_val_for_filters)

st.subheader("Filtros")
st.caption("Ajuste os filtros e clique em Aplicar filtros para atualizar os dados.")

with st.form("form_filtros", clear_on_submit=False):
    # Linha 1
    c1, c2 = st.columns(2)
    with c1:
        uf_input = st.text_input(
            "UF",
            value=st.session_state["filtros_aplicados"]["uf"],
        ).strip().upper()

    with c2:
        mun_options = ["(Todos)"] + municipios if municipios else ["(Todos)"]
        mun_default = st.session_state["filtros_aplicados"]["municipio"] or "(Todos)"
        mun_index = mun_options.index(mun_default) if mun_default in mun_options else 0
        municipio = st.selectbox("Município", mun_options, index=mun_index)

    municipio_val = None if municipio == "(Todos)" else municipio
    bairros_form, locais_form = load_bairros_locais(uf_input, municipio_val)

    # Linha 2
    c3, c4 = st.columns(2)
    with c3:
        tipo_default = st.session_state["filtros_aplicados"]["tipo"]
        tipo_index = tipos.index(tipo_default) if tipo_default in tipos else 0
        tipo = st.selectbox("Tipo de eleição", tipos, index=tipo_index) if tipos else ""

    with c4:
        ano_default = st.session_state["filtros_aplicados"]["ano"]
        ano_index = anos.index(ano_default) if ano_default in anos else 0
        ano = st.selectbox("Ano", anos, index=ano_index) if anos else 0

    # Linha 3
    c5, c6 = st.columns(2)
    with c5:
        turno_default = st.session_state["filtros_aplicados"]["turno"]
        turno_index = turnos.index(turno_default) if turno_default in turnos else 0
        turno = st.selectbox("Turno", turnos, index=turno_index) if turnos else 1

    with c6:
        cargo_default = st.session_state["filtros_aplicados"]["cargo"]
        if cargo_default in cargos:
            cargo_index = cargos.index(cargo_default)
        else:
            cargo_index = cargos.index("VEREADOR") if "VEREADOR" in cargos else 0
        cargo = st.selectbox("Cargo", cargos, index=cargo_index) if cargos else ""

    # Linha 4
    c7, c8 = st.columns(2)
    with c7:
        reg_options = ["(Todas)"] + regionais if regionais else ["(Todas)"]
        reg_default = st.session_state["filtros_aplicados"]["regional"]
        reg_index = reg_options.index(reg_default) if reg_default in reg_options else 0
        regional = st.selectbox("Regional (opcional)", reg_options, index=reg_index)

    with c8:
        if municipio_val is None:
            bairro = "(Todos)"
            st.selectbox("Bairro (opcional)", ["(Todos)"], index=0, disabled=True)
        else:
            bairro_options = ["(Todos)"] + bairros_form if bairros_form else ["(Todos)"]
            bairro_default = st.session_state["filtros_aplicados"]["bairro"]
            bairro_index = bairro_options.index(bairro_default) if bairro_default in bairro_options else 0
            bairro = st.selectbox("Bairro (opcional)", bairro_options, index=bairro_index)

    # Linha 5
    c9, c10 = st.columns(2)
    with c9:
        if municipio_val is None:
            local_votacao = "(Todos)"
            st.selectbox("Local de votação (opcional)", ["(Todos)"], index=0, disabled=True)
        else:
            local_options = ["(Todos)"] + locais_form if locais_form else ["(Todos)"]
            local_default = st.session_state["filtros_aplicados"]["local_votacao"]
            local_index = local_options.index(local_default) if local_default in local_options else 0
            local_votacao = st.selectbox("Local de votação (opcional)", local_options, index=local_index)

    with c10:
        busca = st.text_input(
            "Nome do candidato",
            value=st.session_state["filtros_aplicados"]["busca"],
            placeholder="Digite parte do nome",
        )

    # Linha 6
    c11, c12 = st.columns(2)
    with c11:
        ordem_options = ["Alfabética", "Votos (desc)"]
        ordem_default = st.session_state["filtros_aplicados"]["ordem"]
        ordem_index = ordem_options.index(ordem_default) if ordem_default in ordem_options else 1
        ordem = st.selectbox("Ordenar por", ordem_options, index=ordem_index)

    with c12:
        mostrar_options = ["10", "50", "100", "200", "500", "Todos"]
        mostrar_default = st.session_state["filtros_aplicados"]["mostrar_opcao"]
        mostrar_index = mostrar_options.index(mostrar_default) if mostrar_default in mostrar_options else 0
        mostrar_opcao = st.selectbox("Quantidade de resultados", mostrar_options, index=mostrar_index)

    c_btn1, c_btn2 = st.columns([1, 1])
    with c_btn1:
        aplicar = st.form_submit_button("Aplicar filtros", type="primary")
    with c_btn2:
        limpar_relatorio = st.form_submit_button("Limpar relatório")

if limpar_relatorio:
    st.session_state["relatorio_candidato_nome"] = None
    st.session_state["relatorio_dados"] = None

if aplicar:
    st.session_state["filtros_aplicados"] = {
        "uf": uf_input,
        "municipio": municipio,
        "tipo": tipo,
        "ano": ano,
        "turno": turno,
        "cargo": cargo,
        "regional": regional,
        "bairro": bairro,
        "local_votacao": local_votacao,
        "busca": busca,
        "ordem": ordem,
        "mostrar_opcao": mostrar_opcao,
    }

    # evita mostrar relatório velho com filtros novos
    st.session_state["relatorio_candidato_nome"] = None
    st.session_state["relatorio_dados"] = None

f = st.session_state["filtros_aplicados"]

top_n = None if f["mostrar_opcao"] == "Todos" else int(f["mostrar_opcao"])
params = {
    "ano": f["ano"],
    "tipo": f["tipo"],
    "turno": f["turno"],
    "cargo": f["cargo"],
    "uf": f["uf"],
    "municipio": None if f["municipio"] == "(Todos)" else f["municipio"],
    "regional": None if f["regional"] == "(Todas)" else f["regional"],
    "bairro": None if f["bairro"] == "(Todos)" else f["bairro"],
    "local_votacao": None if f["local_votacao"] == "(Todos)" else f["local_votacao"],
}

if top_n is None:
    st.warning("Exibir todos os registros pode deixar a interface mais lenta.")

st.divider()

# =========================
# Ranking
# =========================
with st.spinner("Carregando ranking..."):
    df = query_ranking(
        params=params,
        order_by_votes=(f["ordem"] == "Votos (desc)"),
        top_n=top_n,
        busca=f["busca"],
    )

# KPIs
st.subheader("Resumo do recorte")

if len(df):
    total_votos = int(df["votos"].sum())
    total_candidatos = int(df["candidato"].nunique())
    lider = df.sort_values(["votos", "candidato"], ascending=[False, True]).iloc[0]["candidato"]
    partido_lider = df.sort_values(["votos", "candidato"], ascending=[False, True]).iloc[0]["partido"]
else:
    total_votos = 0
    total_candidatos = 0
    lider = "-"
    partido_lider = "-"

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total de votos", format_int(total_votos))
k2.metric("Candidatos", format_int(total_candidatos))
k3.metric("Líder", lider)
k4.metric("Partido do líder", partido_lider)

st.caption(
    "O ranking abaixo respeita todos os filtros aplicados. "
    "Já o relatório do candidato desconsidera bairro e local de votação para preservar o total do município no recorte principal."
)

st.divider()

# =========================
# Relatório do candidato
# =========================
if f["busca"] and len(f["busca"].strip()) >= 2:
    with st.spinner("Buscando candidatos..."):
        candidatos_match = list_candidatos_match(params, f["busca"].strip())

    st.subheader("Relatório do candidato")

    if len(candidatos_match) == 0:
        st.info("Nenhum candidato encontrado para essa busca no recorte atual.")
    else:
        cand_default = st.session_state["relatorio_candidato_nome"]
        if cand_default not in candidatos_match:
            cand_default = candidatos_match[0]

        cand_index = candidatos_match.index(cand_default) if cand_default in candidatos_match else 0
        cand_sel = st.selectbox("Selecione o candidato", candidatos_match, index=cand_index)

        c_rel1, c_rel2 = st.columns([1, 1])
        with c_rel1:
            gerar_relatorio = st.button("Gerar relatório do candidato", type="primary")
        with c_rel2:
            limpar_cand = st.button("Limpar seleção do candidato")

        if limpar_cand:
            st.session_state["relatorio_candidato_nome"] = None
            st.session_state["relatorio_dados"] = None

        if gerar_relatorio:
            with st.spinner("Gerando relatório..."):
                rel = query_relatorio_candidato(params, cand_sel)
            st.session_state["relatorio_candidato_nome"] = cand_sel
            st.session_state["relatorio_dados"] = rel

        rel = st.session_state["relatorio_dados"]
        if rel and rel.get("ok"):
            info = rel["info"]

            st.markdown(f"### {info['candidato']}")
            st.caption(f"Partido: {info['partido']} • Cargo: {info['cargo']} • Município: {info['municipio']}")

            cA, cB, cC, cD = st.columns(4)
            cA.metric("Votos totais", format_int(info["votos_totais"]))
            cB.metric("Partido", info["partido"])
            cC.metric("Município", info["municipio"])
            cD.metric("Eleição", f"{info['ano']} • {info['tipo']} • T{info['turno']}")

            t1, t2 = st.columns(2)
            with t1:
                st.markdown("### Top 10 bairros")
                top_bairros = rel["top_bairros"].copy()
                if len(top_bairros):
                    top_bairros["votos"] = top_bairros["votos"].map(format_int)
                st.dataframe(top_bairros, use_container_width=True, hide_index=True)

            with t2:
                st.markdown("### Top 10 locais de votação")
                top_locais = rel["top_locais"].copy()
                if len(top_locais):
                    top_locais["votos"] = top_locais["votos"].map(format_int)
                st.dataframe(top_locais, use_container_width=True, hide_index=True)

            st.markdown("### Top 3 regionais")
            top_regionais = rel["top_regionais"].copy()
            if len(top_regionais):
                top_regionais["votos"] = top_regionais["votos"].map(format_int)
            st.dataframe(top_regionais, use_container_width=True, hide_index=True)

        elif rel and not rel.get("ok"):
            st.warning("Sem dados para esse candidato no recorte atual.")

st.divider()

# =========================
# Tabela + exportação
# =========================
st.subheader("Candidatos")

if len(df) == 0:
    st.info("Nenhum resultado encontrado para os filtros aplicados.")
else:
    df_view = df.copy()
    df_export = df.copy()

    df_view["votos"] = df_view["votos"].map(format_int)

    cta1, cta2 = st.columns([1, 3])
    with cta1:
        st.download_button(
            "Baixar CSV",
            data=df_export.to_csv(index=False).encode("utf-8-sig"),
            file_name="ranking_candidatos.csv",
            mime="text/csv",
        )
    with cta2:
        st.caption(f"{len(df_export)} registro(s) exibido(s) no ranking atual.")

    st.dataframe(df_view, use_container_width=True, hide_index=True, height=520)