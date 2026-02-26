# src/app/ui/dashboard.py
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# =========================
# Import robusto (local + cloud)
# =========================
SRC_DIR = Path(__file__).resolve().parents[2]  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app.db.conn import get_conn  # noqa: E402

# =========================
# Streamlit config + CSS (mobile)
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


@st.cache_data(ttl=60)
def load_filters(uf: str):
    anos = df_query("SELECT DISTINCT ano FROM dim_eleicao ORDER BY ano DESC;")["ano"].tolist()
    tipos = df_query("SELECT DISTINCT tipo FROM dim_eleicao ORDER BY tipo;")["tipo"].tolist()
    turnos = df_query("SELECT DISTINCT turno FROM dim_eleicao ORDER BY turno;")["turno"].tolist()
    cargos = df_query("SELECT DISTINCT cargo FROM dim_eleicao ORDER BY cargo;")["cargo"].tolist()

    municipios = df_query(
        "SELECT nome FROM dim_municipio WHERE uf = %(uf)s ORDER BY nome;",
        {"uf": uf},
    )["nome"].tolist()

    regionais = df_query("SELECT nome FROM dim_regional ORDER BY nome;")["nome"].tolist()

    return anos, tipos, turnos, cargos, municipios, regionais


@st.cache_data(ttl=60)
def load_bairros_locais(uf: str, municipio: str | None):
    if not municipio:
        return [], []

    bairros_df = df_query(
        """
        SELECT DISTINCT b.nome
        FROM dim_bairro b
        JOIN dim_municipio m ON m.id_municipio = b.id_municipio
        WHERE m.uf = %(uf)s AND upper(m.nome) = upper(%(municipio)s)
          AND b.nome IS NOT NULL AND trim(b.nome) <> ''
        ORDER BY b.nome;
        """,
        {"uf": uf, "municipio": municipio},
    )

    locais_df = df_query(
        """
        SELECT DISTINCT l.nome
        FROM dim_local_votacao l
        JOIN dim_municipio m ON m.id_municipio = l.id_municipio
        WHERE m.uf = %(uf)s AND upper(m.nome) = upper(%(municipio)s)
          AND l.nome IS NOT NULL AND trim(l.nome) <> ''
        ORDER BY l.nome;
        """,
        {"uf": uf, "municipio": municipio},
    )

    bairros = bairros_df["nome"].tolist() if len(bairros_df) else []
    locais = locais_df["nome"].tolist() if len(locais_df) else []
    return bairros, locais


def query_ranking(params: dict, order_by_votes: bool) -> pd.DataFrame:
    order_sql = "ORDER BY votos DESC, candidato ASC" if order_by_votes else "ORDER BY candidato ASC"
    sql = f"""
    SELECT
      c.nome AS candidato,
      p.sigla AS partido,
      SUM(f.votos) AS votos
    FROM fato_votos_local f
    JOIN dim_candidato c ON c.id_candidato = f.id_candidato
    JOIN dim_partido p ON p.id_partido = c.id_partido
    JOIN dim_eleicao e ON e.id_eleicao = f.id_eleicao
    JOIN dim_municipio m ON m.id_municipio = f.id_municipio
    JOIN dim_local_votacao l ON l.id_local = f.id_local
    LEFT JOIN dim_bairro b ON b.id_bairro = l.id_bairro
    LEFT JOIN dim_regional r ON r.id_regional = b.id_regional
    WHERE
      e.ano = %(ano)s
      AND e.tipo = %(tipo)s
      AND e.turno = %(turno)s
      AND e.cargo = %(cargo)s
      AND m.uf = %(uf)s
      AND upper(m.nome) = upper(COALESCE(%(municipio)s, m.nome))
      AND upper(COALESCE(r.nome, '')) = upper(COALESCE(%(regional)s, COALESCE(r.nome, '')))
      AND upper(COALESCE(b.nome, '')) = upper(COALESCE(%(bairro)s, COALESCE(b.nome, '')))
      AND upper(l.nome) = upper(COALESCE(%(local_votacao)s, l.nome))
    GROUP BY c.nome, p.sigla
    {order_sql};
    """
    return df_query(sql, params)


def get_secret(key: str, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def list_candidatos_match(params: dict, termo: str) -> list[str]:
    sql = """
    SELECT DISTINCT c.nome AS candidato
    FROM fato_votos_local f
    JOIN dim_candidato c ON c.id_candidato = f.id_candidato
    JOIN dim_eleicao e ON e.id_eleicao = f.id_eleicao
    JOIN dim_municipio m ON m.id_municipio = f.id_municipio
    WHERE
      e.ano = %(ano)s
      AND e.tipo = %(tipo)s
      AND e.turno = %(turno)s
      AND e.cargo = %(cargo)s
      AND m.uf = %(uf)s
      AND upper(m.nome) = upper(COALESCE(%(municipio)s, m.nome))
      AND c.nome ILIKE %(q)s
    ORDER BY 1;
    """
    df = df_query(sql, {**params, "q": f"%{termo}%"} )
    return df["candidato"].tolist() if len(df) else []


def query_relatorio_candidato(params: dict, candidato: str) -> dict:
    p = dict(params)
    p["candidato"] = candidato
    # não “corta” o relatório
    p["bairro"] = None
    p["local_votacao"] = None

    sql_total = """
    SELECT
      c.nome AS candidato,
      p.sigla AS partido,
      m.nome AS municipio,
      e.ano,
      e.tipo,
      e.turno,
      e.cargo,
      SUM(f.votos) AS votos_totais
    FROM fato_votos_local f
    JOIN dim_candidato c ON c.id_candidato = f.id_candidato
    JOIN dim_partido p ON p.id_partido = c.id_partido
    JOIN dim_eleicao e ON e.id_eleicao = f.id_eleicao
    JOIN dim_municipio m ON m.id_municipio = f.id_municipio
    JOIN dim_local_votacao l ON l.id_local = f.id_local
    LEFT JOIN dim_bairro b ON b.id_bairro = l.id_bairro
    LEFT JOIN dim_regional r ON r.id_regional = b.id_regional
    WHERE
      e.ano = %(ano)s
      AND e.tipo = %(tipo)s
      AND e.turno = %(turno)s
      AND e.cargo = %(cargo)s
      AND m.uf = %(uf)s
      AND upper(m.nome) = upper(COALESCE(%(municipio)s, m.nome))
      AND upper(COALESCE(r.nome, '')) = upper(COALESCE(%(regional)s, COALESCE(r.nome, '')))
      AND c.nome = %(candidato)s
    GROUP BY c.nome, p.sigla, m.nome, e.ano, e.tipo, e.turno, e.cargo;
    """
    info = df_query(sql_total, p)
    if not len(info):
        return {"ok": False}

    sql_bairros = """
    SELECT
      COALESCE(b.nome, '(Sem bairro)') AS bairro,
      SUM(f.votos) AS votos
    FROM fato_votos_local f
    JOIN dim_candidato c ON c.id_candidato = f.id_candidato
    JOIN dim_eleicao e ON e.id_eleicao = f.id_eleicao
    JOIN dim_municipio m ON m.id_municipio = f.id_municipio
    JOIN dim_local_votacao l ON l.id_local = f.id_local
    LEFT JOIN dim_bairro b ON b.id_bairro = l.id_bairro
    LEFT JOIN dim_regional r ON r.id_regional = b.id_regional
    WHERE
      e.ano = %(ano)s
      AND e.tipo = %(tipo)s
      AND e.turno = %(turno)s
      AND e.cargo = %(cargo)s
      AND m.uf = %(uf)s
      AND upper(m.nome) = upper(COALESCE(%(municipio)s, m.nome))
      AND upper(COALESCE(r.nome, '')) = upper(COALESCE(%(regional)s, COALESCE(r.nome, '')))
      AND c.nome = %(candidato)s
    GROUP BY 1
    ORDER BY votos DESC
    LIMIT 10;
    """
    top_bairros = df_query(sql_bairros, p)

    sql_locais = """
    SELECT
      l.nome AS local_votacao,
      SUM(f.votos) AS votos
    FROM fato_votos_local f
    JOIN dim_candidato c ON c.id_candidato = f.id_candidato
    JOIN dim_eleicao e ON e.id_eleicao = f.id_eleicao
    JOIN dim_municipio m ON m.id_municipio = f.id_municipio
    JOIN dim_local_votacao l ON l.id_local = f.id_local
    LEFT JOIN dim_bairro b ON b.id_bairro = l.id_bairro
    LEFT JOIN dim_regional r ON r.id_regional = b.id_regional
    WHERE
      e.ano = %(ano)s
      AND e.tipo = %(tipo)s
      AND e.turno = %(turno)s
      AND e.cargo = %(cargo)s
      AND m.uf = %(uf)s
      AND upper(m.nome) = upper(COALESCE(%(municipio)s, m.nome))
      AND upper(COALESCE(r.nome, '')) = upper(COALESCE(%(regional)s, COALESCE(r.nome, '')))
      AND c.nome = %(candidato)s
    GROUP BY 1
    ORDER BY votos DESC
    LIMIT 10;
    """
    top_locais = df_query(sql_locais, p)

    sql_regionais = """
    SELECT
      COALESCE(r.nome, '(Sem regional)') AS regional,
      SUM(f.votos) AS votos
    FROM fato_votos_local f
    JOIN dim_candidato c ON c.id_candidato = f.id_candidato
    JOIN dim_eleicao e ON e.id_eleicao = f.id_eleicao
    JOIN dim_municipio m ON m.id_municipio = f.id_municipio
    JOIN dim_local_votacao l ON l.id_local = f.id_local
    LEFT JOIN dim_bairro b ON b.id_bairro = l.id_bairro
    LEFT JOIN dim_regional r ON r.id_regional = b.id_regional
    WHERE
      e.ano = %(ano)s
      AND e.tipo = %(tipo)s
      AND e.turno = %(turno)s
      AND e.cargo = %(cargo)s
      AND m.uf = %(uf)s
      AND upper(m.nome) = upper(COALESCE(%(municipio)s, m.nome))
      AND c.nome = %(candidato)s
    GROUP BY 1
    ORDER BY votos DESC
    LIMIT 3;
    """
    top_regionais = df_query(sql_regionais, p)

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
                cur.execute("SELECT 1 FROM dim_eleicao LIMIT 1;")
                st.success("Tabela dim_eleicao OK")
    except Exception as e:
        st.error("Falha ao conectar ou consultar tabelas.")
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
    mostrar_opcao = st.selectbox("Mostrar quantos?", ["10","50", "100", "200", "500", "Todos"], index=0)
    top_n = None if mostrar_opcao == "Todos" else int(mostrar_opcao)

# ✅ params AGORA existe antes de usar na busca/relatório
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

df = query_ranking(params, order_by_votes=(ordem == "Votos (desc)"))

if busca:
    df = df[df["candidato"].str.contains(busca, case=False, na=False)]

if top_n is None:
    st.dataframe(df, use_container_width=True, hide_index=True, height=520)
else:
    st.dataframe(df.head(top_n), use_container_width=True, hide_index=True, height=520)