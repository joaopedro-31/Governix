from __future__ import annotations

import streamlit as st

from app.ui.eleitoral.helpers import first_or, is_estadual, is_municipal
from app.ui.eleitoral.queries import load_bairros_locais, load_dependent_filters, load_tipos
from app.ui.eleitoral.state import get_secret, reset_secondary_filters_from_primary


def render_filters():
    st.subheader("Filtros")
    st.caption("UF e Tipo de eleição controlam os demais filtros.")

    f = st.session_state["filtros_aplicados"]
    default_municipio = get_secret("MUNICIPIO_PADRAO", "FORTALEZA")
    
    p1, p2 = st.columns(2)

    with p1:
        uf_input = st.text_input(
            "UF",
            value=f["uf"],
            key="uf_primary_input",
        ).strip().upper()

    with p2:
        tipos_disponiveis = load_tipos(uf_input) if uf_input else []
        tipo_atual = first_or(f["tipo"], tipos_disponiveis)
        tipo = (
            st.selectbox(
                "Tipo de eleição",
                tipos_disponiveis,
                index=tipos_disponiveis.index(tipo_atual) if tipo_atual in tipos_disponiveis else 0,
                key="tipo_primary_select",
            )
            if tipos_disponiveis
            else None
        )

    if uf_input != f["uf"] or tipo != f["tipo"]:
        f["uf"] = uf_input
        f["tipo"] = tipo
        reset_secondary_filters_from_primary()
        f = st.session_state["filtros_aplicados"]

    if f["tipo"]:
        anos, turnos, cargos, municipios, regionais = load_dependent_filters(f["uf"], f["tipo"])
    else:
        anos, turnos, cargos, municipios, regionais = [], [], [], [], []

    with st.form("form_filtros_secundarios", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            ano = st.selectbox(
                "Ano",
                anos,
                index=anos.index(first_or(f["ano"], anos)) if anos else 0,
            ) if anos else None

        with c2:
            turno = st.selectbox(
                "Turno",
                turnos,
                index=turnos.index(first_or(f["turno"], turnos)) if turnos else 0,
            ) if turnos else None

        c3, c4 = st.columns(2)
        with c3:
            cargo_pref = f["cargo"]
            if cargo_pref not in cargos and "VEREADOR" in cargos:
                cargo_pref = "VEREADOR"

            cargo = st.selectbox(
                "Cargo",
                cargos,
                index=cargos.index(first_or(cargo_pref, cargos)) if cargos else 0,
            ) if cargos else None

        with c4:
            if is_municipal(f["tipo"]):
                municipio = st.selectbox(
                    "Município",
                    [default_municipio],
                    index=0,
                    disabled=True,
                )
            else:
                mun_options = ["(Todos)"] + municipios if municipios else ["(Todos)"]
                mun_default = f["municipio"] if f["municipio"] in mun_options else "(Todos)"
                municipio = st.selectbox(
                    "Município",
                    mun_options,
                    index=mun_options.index(mun_default),
                )

        municipio_val = None if municipio == "(Todos)" else municipio
        bairros_form, locais_form = load_bairros_locais(f["uf"], municipio_val)

        if not is_estadual(f["tipo"]):
            c5, c6 = st.columns(2)

            with c5:
                reg_options = ["(Todas)"] + regionais if regionais else ["(Todas)"]
                reg_default = f["regional"] if f["regional"] in reg_options else "(Todas)"
                regional = st.selectbox(
                    "Regional (opcional)",
                    reg_options,
                    index=reg_options.index(reg_default),
                )

            with c6:
                if municipio_val is None:
                    bairro = "(Todos)"
                    st.selectbox("Bairro (opcional)", ["(Todos)"], index=0, disabled=True)
                else:
                    bairro_options = ["(Todos)"] + bairros_form if bairros_form else ["(Todos)"]
                    bairro_default = f["bairro"] if f["bairro"] in bairro_options else "(Todos)"
                    bairro = st.selectbox(
                        "Bairro (opcional)",
                        bairro_options,
                        index=bairro_options.index(bairro_default),
                    )
        else:
            regional = "(Todas)"
            bairro = "(Todos)"

        c7, c8 = st.columns(2)
        with c7:
            if municipio_val is None:
                local_votacao = "(Todos)"
                st.selectbox("Local de votação (opcional)", ["(Todos)"], index=0, disabled=True)
            else:
                local_options = ["(Todos)"] + locais_form if locais_form else ["(Todos)"]
                local_default = f["local_votacao"] if f["local_votacao"] in local_options else "(Todos)"
                local_votacao = st.selectbox(
                    "Local de votação (opcional)",
                    local_options,
                    index=local_options.index(local_default),
                )

        with c8:
            busca = st.text_input(
                "Nome do candidato",
                value=f["busca"],
                placeholder="Digite parte do nome",
            )

        c9, c10 = st.columns(2)
        with c9:
            ordem_votos = st.selectbox(
                "Ordenar votos",
                ["DESC", "ASC"],
                index=0 if f["ordem_votos"] == "DESC" else 1,
            )

        with c10:
            mostrar_options = ["10", "50", "100", "200", "500", "Todos"]
            mostrar_default = f["mostrar_opcao"]
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
            "uf": f["uf"],
            "tipo": f["tipo"],
            "ano": ano,
            "turno": turno,
            "cargo": cargo,
            "municipio": municipio,
            "regional": regional,
            "bairro": bairro,
            "local_votacao": local_votacao,
            "busca": busca,
            "ordem_votos": ordem_votos,
            "mostrar_opcao": mostrar_opcao,
        }

        st.session_state["relatorio_candidato_nome"] = None
        st.session_state["relatorio_dados"] = None

    return st.session_state["filtros_aplicados"]