# src/app/ui/dashboard.py

import pandas as pd
import streamlit as st

from app.db.conn import get_conn  # garanta PYTHONPATH=. ao rodar

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
# DB helpers (conexão curta por query -> evita transação abortada)
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
    """
    Carrega listas de Bairro e Local de votação de forma "cascata" pelo município
    para evitar selects gigantes.
    """
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

      -- filtros opcionais (sem AmbiguousParameter)
      AND upper(m.nome) = upper(COALESCE(%(municipio)s, m.nome))
      AND upper(COALESCE(r.nome, '')) = upper(COALESCE(%(regional)s, COALESCE(r.nome, '')))
      AND upper(COALESCE(b.nome, '')) = upper(COALESCE(%(bairro)s, COALESCE(b.nome, '')))
      AND upper(l.nome) = upper(COALESCE(%(local_votacao)s, l.nome))

    GROUP BY c.nome, p.sigla
    {order_sql};
    """
    return df_query(sql, params)


def query_top1(params: dict) -> pd.DataFrame:
    sql = """
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

      -- filtros opcionais (sem AmbiguousParameter)
      AND upper(m.nome) = upper(COALESCE(%(municipio)s, m.nome))
      AND upper(COALESCE(r.nome, '')) = upper(COALESCE(%(regional)s, COALESCE(r.nome, '')))
      AND upper(COALESCE(b.nome, '')) = upper(COALESCE(%(bairro)s, COALESCE(b.nome, '')))
      AND upper(l.nome) = upper(COALESCE(%(local_votacao)s, l.nome))

    GROUP BY c.nome, p.sigla
    ORDER BY votos DESC, candidato ASC
    LIMIT 1;
    """
    return df_query(sql, params)


# =========================
# UI
# =========================
st.title("GOVERNIX • Dashboard Eleitoral")

# Sidebar: apenas avançado
default_uf = "CE"
with st.sidebar:
    st.header("Filtros avançados")
    uf = st.text_input("UF", value=default_uf).strip().upper()

anos, tipos, turnos, cargos, municipios, regionais = load_filters(uf)

with st.sidebar:
    tipo = st.selectbox("Tipo", tipos) if tipos else ""
    turno = st.selectbox("Turno", turnos) if turnos else 1
    municipio = st.selectbox("Município", ["(Todos)"] + municipios) if municipios else "(Todos)"

municipio_val = None if municipio == "(Todos)" else municipio
bairros, locais = load_bairros_locais(uf, municipio_val)

# Corpo: principais
st.subheader("Filtros principais")

col1, col2 = st.columns(2)
with col1:
    ano = st.selectbox("Ano", anos) if anos else 0
    cargo = st.selectbox("Cargo", cargos) if cargos else ""
with col2:
    regional = st.selectbox("Regional (opcional)", ["(Todas)"] + regionais) if regionais else "(Todas)"
    busca = st.text_input("Buscar candidato (contém)")

col5, col6 = st.columns(2)
with col5:
    bairro = st.selectbox("Bairro (opcional)", ["(Todos)"] + bairros) if bairros else "(Todos)"
with col6:
    local_votacao = st.selectbox("Local de votação (opcional)", ["(Todos)"] + locais) if locais else "(Todos)"

col3, col4 = st.columns(2)
with col3:
    ordem = st.selectbox("Ordenação", ["Alfabética", "Votos (desc)"])
with col4:
    top_n = st.slider("Mostrar quantos?", min_value=20, max_value=500, value=50, step=10)

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

# Perguntas rápidas (mobile friendly)
# st.subheader("Perguntas rápidas")

# def run_quick(cargo_override: str, regional_override: str | None):
#     p = dict(params)
#     p["cargo"] = cargo_override
#     p["regional"] = regional_override

#     # perguntas rápidas normalmente ignoram filtros muito específicos
#     p["bairro"] = None
#     p["local_votacao"] = None

#     top = query_top1(p)
#     if len(top) == 0:
#         st.warning("Sem dados para esse recorte.")
#         return
#     st.success(
#         f"{cargo_override} mais votado"
#         + (f" em {regional_override}" if regional_override else "")
#         + f": {top.loc[0,'candidato']} ({top.loc[0,'partido']}) • {int(top.loc[0,'votos'])} votos"
#     )

# with st.expander("Abrir / fechar", expanded=True):
#     if st.button("Vereador mais votado (Regional 6)"):
#         run_quick("VEREADOR", "REGIONAL 6")

#     if st.button("Vereador mais votado (no recorte atual)"):
#         run_quick("VEREADOR", params["regional"])

#     if st.button("Top 1 (no recorte atual)"):
#         top = query_top1(params)
#         if len(top):
#             st.info(f"{top.loc[0,'candidato']} ({top.loc[0,'partido']}) • {int(top.loc[0,'votos'])} votos")
#         else:
#             st.warning("Sem dados para esse recorte.")

# Tabela
st.subheader("Candidatos")

df = query_ranking(params, order_by_votes=(ordem == "Votos (desc)"))

if busca:
    df = df[df["candidato"].str.contains(busca, case=False, na=False)]

st.dataframe(df.head(top_n), use_container_width=True, hide_index=True, height=520)