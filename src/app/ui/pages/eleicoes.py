from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[3]  # .../Governix/src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
    
import streamlit as st

from app.db.conn import get_conn
from app.ui.eleitoral.filters import render_filters
from app.ui.eleitoral.helpers import format_int
from app.ui.eleitoral.queries import (
    list_candidatos_match,
    query_ranking,
    query_relatorio_candidato,
)
from app.ui.eleitoral.state import init_session_state
from app.ui.eleitoral.ui import inject_css, set_page

set_page()
inject_css()
init_session_state()

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

f = render_filters()

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

with st.spinner("Carregando ranking..."):
    df = query_ranking(
        params=params,
        votes_sort_direction=f["ordem_votos"],
        top_n=top_n,
        busca=f["busca"],
    )

st.subheader("Resumo do recorte")

if len(df):
    df_sorted = df.sort_values(["votos", "candidato"], ascending=[False, True])
    total_votos = int(df["votos"].sum())
    total_candidatos = int(df["candidato"].nunique())
    lider = df_sorted.iloc[0]["candidato"]
    partido_lider = df_sorted.iloc[0]["partido"]
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