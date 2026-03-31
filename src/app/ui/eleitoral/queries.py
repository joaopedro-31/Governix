from __future__ import annotations

import pandas as pd
import streamlit as st

from app.db.conn import get_conn


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


def build_where_and_params(
    base_params: dict,
    busca: str | None = None,
    candidato: str | None = None,
):
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


@st.cache_data(ttl=300)
def load_tipos(uf: str):
    df = df_query(
        """
        SELECT DISTINCT tipo
        FROM mv_ranking_candidato
        WHERE uf = %(uf)s
        ORDER BY tipo DESC;
        """,
        {"uf": uf},
    )
    return df["tipo"].tolist() if len(df) else []


@st.cache_data(ttl=300)
def load_dependent_filters(uf: str, tipo: str):
    params = {"uf": uf, "tipo": tipo}

    anos_df = df_query(
        """
        SELECT DISTINCT ano
        FROM mv_ranking_candidato
        WHERE uf = %(uf)s
          AND tipo = %(tipo)s
        ORDER BY ano;
        """,
        params,
    )

    turnos_df = df_query(
        """
        SELECT DISTINCT turno
        FROM mv_ranking_candidato
        WHERE uf = %(uf)s
          AND tipo = %(tipo)s
        ORDER BY turno;
        """,
        params,
    )

    cargos_df = df_query(
        """
        SELECT DISTINCT cargo
        FROM mv_ranking_candidato
        WHERE uf = %(uf)s
          AND tipo = %(tipo)s
        ORDER BY cargo;
        """,
        params,
    )

    municipios_df = df_query(
        """
        SELECT DISTINCT municipio
        FROM mv_ranking_candidato
        WHERE uf = %(uf)s
          AND tipo = %(tipo)s
        ORDER BY municipio;
        """,
        params,
    )

    regionais_df = df_query(
        """
        SELECT DISTINCT regional
        FROM mv_ranking_candidato
        WHERE uf = %(uf)s
          AND tipo = %(tipo)s
          AND regional <> ''
        ORDER BY regional;
        """,
        params,
    )

    anos = anos_df["ano"].tolist() if len(anos_df) else []
    turnos = turnos_df["turno"].tolist() if len(turnos_df) else []
    cargos = cargos_df["cargo"].tolist() if len(cargos_df) else []
    municipios = municipios_df["municipio"].tolist() if len(municipios_df) else []
    regionais = regionais_df["regional"].tolist() if len(regionais_df) else []

    return anos, turnos, cargos, municipios, regionais


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


@st.cache_data(ttl=60)
def query_ranking(
    params: dict,
    votes_sort_direction: str,
    top_n: int | None,
    busca: str | None = None,
) -> pd.DataFrame:
    where, sql_params = build_where_and_params(params, busca=busca)

    direction = "ASC" if str(votes_sort_direction).upper() == "ASC" else "DESC"
    order_sql = f"ORDER BY votos {direction}, candidato ASC"

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
        CASE
            WHEN local_votacao IS NULL OR local_votacao = '' THEN '(Sem local)'
            ELSE local_votacao
        END AS local_votacao,
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