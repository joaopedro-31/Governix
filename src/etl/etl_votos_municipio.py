import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
import psycopg


# =========================
# CONFIGURAÇÕES
# =========================
load_dotenv()

PG_CONFIG = {
    "host": os.getenv("PGHOST"),
    "port": int(os.getenv("PGPORT", "5432")),
    "dbname": os.getenv("PGDATABASE"),
    "user": os.getenv("PGUSER"),
    "password": os.getenv("PGPASSWORD"),
    "sslmode": os.getenv("PGSSLMODE", "require"),
}

CSV_MUNICIPAL = os.getenv("CSV_CAMINHO")
CSV_ESTADUAL = os.getenv("CSV_CAMINHO_ESTADUAL")

UF_PADRAO = os.getenv("UF_PADRAO", "CE").strip().upper()

TIPO_ELEICAO_MUNICIPAL = os.getenv("TIPO_ELEICAO", "municipal")
TIPO_ELEICAO_ESTADUAL = os.getenv("TIPO_ELEICAO_ESTADUAL", "estadual")

ETL_MODE = os.getenv("ETL_MODE", "municipal").strip().lower()


# =========================
# CONEXÃO
# =========================
def conectar():
    return psycopg.connect(**PG_CONFIG)


def executar_sql(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)


def consultar_valor(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None


def contar_linhas(conn, tabela):
    total = consultar_valor(conn, f"SELECT COUNT(*) FROM {tabela};")
    print(f"▶ {tabela}: {total} linhas")


def amostra_staging(conn, tabela: str, limit: int = 5):
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {tabela} LIMIT %s;", (limit,))
        rows = cur.fetchall()
        print(f"▶ Amostra {tabela} (top {limit}):")
        for r in rows:
            print(r)


# =========================
# DDL BASE
# =========================
DDL_SQL = """
CREATE TABLE IF NOT EXISTS stg_votos_municipio (
  ano INT,
  turno INT,
  cargo TEXT,
  municipio TEXT,
  candidato TEXT,
  partido TEXT,
  votos INT,
  local_votacao TEXT,
  bairro TEXT,
  regional TEXT
);

CREATE TABLE IF NOT EXISTS stg_votos_estaduais (
  ano INT,
  turno INT,
  cargo TEXT,
  municipio TEXT,
  candidato TEXT,
  partido TEXT,
  votos INT,
  local_votacao TEXT,
  bairro TEXT,
  regional TEXT,
  uf CHAR(2)
);

CREATE TABLE IF NOT EXISTS dim_eleicao (
  id_eleicao BIGSERIAL PRIMARY KEY,
  ano INT NOT NULL,
  tipo TEXT NOT NULL,
  turno INT NOT NULL,
  cargo TEXT NOT NULL,
  UNIQUE (ano, tipo, turno, cargo)
);

CREATE TABLE IF NOT EXISTS dim_municipio (
  id_municipio BIGSERIAL PRIMARY KEY,
  nome TEXT NOT NULL,
  uf CHAR(2) NOT NULL,
  UNIQUE (nome, uf)
);

CREATE TABLE IF NOT EXISTS dim_regional (
  id_regional BIGSERIAL PRIMARY KEY,
  nome TEXT NOT NULL,
  UNIQUE (nome)
);

CREATE TABLE IF NOT EXISTS dim_bairro (
  id_bairro BIGSERIAL PRIMARY KEY,
  id_municipio BIGINT REFERENCES dim_municipio(id_municipio),
  nome TEXT NOT NULL,
  id_regional BIGINT REFERENCES dim_regional(id_regional),
  UNIQUE (id_municipio, nome)
);

CREATE TABLE IF NOT EXISTS dim_local_votacao (
  id_local BIGSERIAL PRIMARY KEY,
  id_municipio BIGINT REFERENCES dim_municipio(id_municipio),
  nome TEXT NOT NULL,
  id_bairro BIGINT REFERENCES dim_bairro(id_bairro),
  UNIQUE (id_municipio, nome)
);

CREATE TABLE IF NOT EXISTS dim_partido (
  id_partido BIGSERIAL PRIMARY KEY,
  sigla TEXT NOT NULL,
  UNIQUE (sigla)
);

CREATE TABLE IF NOT EXISTS dim_candidato (
  id_candidato BIGSERIAL PRIMARY KEY,
  nome TEXT NOT NULL,
  numero INT,
  id_partido BIGINT REFERENCES dim_partido(id_partido),
  id_eleicao BIGINT REFERENCES dim_eleicao(id_eleicao),
  id_municipio BIGINT REFERENCES dim_municipio(id_municipio),
  UNIQUE (nome, id_eleicao, id_municipio)
);

CREATE TABLE IF NOT EXISTS fato_votos_local (
  id_fato BIGSERIAL PRIMARY KEY,
  id_eleicao BIGINT REFERENCES dim_eleicao(id_eleicao),
  id_municipio BIGINT REFERENCES dim_municipio(id_municipio),
  id_candidato BIGINT REFERENCES dim_candidato(id_candidato),
  id_local BIGINT REFERENCES dim_local_votacao(id_local),
  votos INT NOT NULL,
  UNIQUE (id_eleicao, id_municipio, id_candidato, id_local)
);
"""

INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_fvl_eleicao ON fato_votos_local (id_eleicao);
CREATE INDEX IF NOT EXISTS idx_fvl_municipio ON fato_votos_local (id_municipio);
CREATE INDEX IF NOT EXISTS idx_fvl_candidato ON fato_votos_local (id_candidato);
CREATE INDEX IF NOT EXISTS idx_fvl_local ON fato_votos_local (id_local);

CREATE INDEX IF NOT EXISTS idx_fvl_eleicao_municipio ON fato_votos_local (id_eleicao, id_municipio);
CREATE INDEX IF NOT EXISTS idx_fvl_eleicao_candidato ON fato_votos_local (id_eleicao, id_candidato);
CREATE INDEX IF NOT EXISTS idx_fvl_municipio_candidato ON fato_votos_local (id_municipio, id_candidato);

CREATE INDEX IF NOT EXISTS idx_dim_eleicao_filtro ON dim_eleicao (ano, tipo, turno, cargo);
CREATE INDEX IF NOT EXISTS idx_dim_municipio_uf_nome ON dim_municipio (uf, nome);
CREATE INDEX IF NOT EXISTS idx_dim_candidato_eleicao_municipio ON dim_candidato (id_eleicao, id_municipio);
CREATE INDEX IF NOT EXISTS idx_dim_candidato_partido ON dim_candidato (id_partido);
CREATE INDEX IF NOT EXISTS idx_dim_local_municipio ON dim_local_votacao (id_municipio);
CREATE INDEX IF NOT EXISTS idx_dim_bairro_municipio ON dim_bairro (id_municipio);
CREATE INDEX IF NOT EXISTS idx_dim_bairro_regional ON dim_bairro (id_regional);
"""

MV_SQL = """
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_ranking_candidato AS
SELECT
    e.ano,
    e.tipo,
    e.turno,
    e.cargo,
    m.uf,
    m.nome AS municipio,
    COALESCE(r.nome, '') AS regional,
    COALESCE(b.nome, '') AS bairro,
    l.nome AS local_votacao,
    c.nome AS candidato,
    p.sigla AS partido,
    SUM(f.votos) AS votos
FROM fato_votos_local f
JOIN dim_candidato c
  ON c.id_candidato = f.id_candidato
JOIN dim_partido p
  ON p.id_partido = c.id_partido
JOIN dim_eleicao e
  ON e.id_eleicao = f.id_eleicao
JOIN dim_municipio m
  ON m.id_municipio = f.id_municipio
JOIN dim_local_votacao l
  ON l.id_local = f.id_local
LEFT JOIN dim_bairro b
  ON b.id_bairro = l.id_bairro
LEFT JOIN dim_regional r
  ON r.id_regional = b.id_regional
GROUP BY
    e.ano,
    e.tipo,
    e.turno,
    e.cargo,
    m.uf,
    m.nome,
    COALESCE(r.nome, ''),
    COALESCE(b.nome, ''),
    l.nome,
    c.nome,
    p.sigla
WITH NO DATA;
"""

MV_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_mv_rank_filtro
ON mv_ranking_candidato (ano, tipo, turno, cargo, uf, municipio);

CREATE INDEX IF NOT EXISTS idx_mv_rank_regional
ON mv_ranking_candidato (regional);

CREATE INDEX IF NOT EXISTS idx_mv_rank_bairro
ON mv_ranking_candidato (bairro);

CREATE INDEX IF NOT EXISTS idx_mv_rank_local
ON mv_ranking_candidato (local_votacao);

CREATE INDEX IF NOT EXISTS idx_mv_rank_candidato
ON mv_ranking_candidato (candidato);

CREATE INDEX IF NOT EXISTS idx_mv_rank_votos
ON mv_ranking_candidato (votos);
"""


# =========================
# BOOTSTRAP ESTRUTURA
# =========================
def garantir_estrutura():
    print("▶ Criando/ajustando tabelas...")
    with conectar() as conn:
        executar_sql(conn, DDL_SQL)
        conn.commit()

    # print("▶ Criando índices...")
    # with conectar() as conn:
    #     executar_sql(conn, INDEX_SQL)
    #     conn.commit()

    print("▶ Criando materialized view...")
    with conectar() as conn:
        executar_sql(conn, MV_SQL)
        conn.commit()


def garantir_indices_mv():
    print("▶ Criando índices da materialized view...")
    with conectar() as conn:
        executar_sql(conn, MV_INDEX_SQL)
        conn.commit()


# =========================
# COPY
# =========================
def carregar_csv_para_staging(tabela: str, colunas: list[str], csv_path: Path):
    if not csv_path or not csv_path.exists():
        raise FileNotFoundError(f"CSV não encontrado: {csv_path}")

    total_linhas = 0

    with conectar() as conn:
        executar_sql(conn, f"TRUNCATE TABLE {tabela};")

        cols_sql = ", ".join(colunas)
        copy_sql = f"""
            COPY {tabela} ({cols_sql})
            FROM STDIN
            WITH (FORMAT csv, HEADER true, DELIMITER ',', ENCODING 'UTF8');
        """

        with conn.cursor() as cur, open(csv_path, "r", encoding="utf-8") as f:
            with cur.copy(copy_sql) as cp:
                for total_linhas, linha in enumerate(f, start=1):
                    cp.write(linha)
                    if total_linhas % 100000 == 0:
                        print(f"▶ {total_linhas:,} linhas enviadas para {tabela}")

        print(f"✅ Carga concluída: {total_linhas:,} linhas enviadas")
        contar_linhas(conn, tabela)
        amostra_staging(conn, tabela, limit=5)


# =========================
# POPULAR DIMENSÕES + FATO
# =========================
def popular_dimensoes_e_fato(stg_table: str, tipo_eleicao: str, uf_mode: str):
    """
    uf_mode:
      - "padrao": usa UF_PADRAO
      - "coluna": usa s.uf
    """
    if uf_mode not in ("padrao", "coluna"):
        raise ValueError("uf_mode inválido. Use 'padrao' ou 'coluna'.")

    uf_select = "%s" if uf_mode == "padrao" else "upper(trim(s.uf))"
    uf_join = "%s" if uf_mode == "padrao" else "upper(trim(s.uf))"
    params_uf = (UF_PADRAO,) if uf_mode == "padrao" else ()

    with conectar() as conn:
        print("▶ Atualizando dim_eleicao...", datetime.now())
        executar_sql(
            conn,
            f"""
            INSERT INTO dim_eleicao (ano, tipo, turno, cargo)
            SELECT DISTINCT
                s.ano,
                %s AS tipo,
                s.turno,
                trim(s.cargo) AS cargo
            FROM {stg_table} s
            WHERE s.ano IS NOT NULL
              AND s.turno IS NOT NULL
              AND s.cargo IS NOT NULL
              AND trim(s.cargo) <> ''
            ON CONFLICT DO NOTHING;
            """,
            (tipo_eleicao,),
        )

        print("▶ Atualizando dim_municipio...", datetime.now())
        executar_sql(
            conn,
            f"""
            INSERT INTO dim_municipio (nome, uf)
            SELECT DISTINCT
                trim(s.municipio) AS nome,
                {uf_select} AS uf
            FROM {stg_table} s
            WHERE s.municipio IS NOT NULL
              AND trim(s.municipio) <> ''
            ON CONFLICT DO NOTHING;
            """,
            params_uf if uf_mode == "padrao" else None,
        )

        print("▶ Atualizando dim_regional...", datetime.now())
        executar_sql(
            conn,
            f"""
            INSERT INTO dim_regional (nome)
            SELECT DISTINCT trim(s.regional)
            FROM {stg_table} s
            WHERE s.regional IS NOT NULL
              AND trim(s.regional) <> ''
            ON CONFLICT DO NOTHING;
            """,
        )

        print("▶ Atualizando dim_bairro...", datetime.now())
        executar_sql(
            conn,
            f"""
            INSERT INTO dim_bairro (id_municipio, nome, id_regional)
            SELECT DISTINCT
                m.id_municipio,
                trim(s.bairro) AS nome,
                r.id_regional
            FROM {stg_table} s
            JOIN dim_municipio m
              ON upper(m.nome) = upper(trim(s.municipio))
             AND m.uf = {uf_join}
            LEFT JOIN dim_regional r
              ON r.nome = trim(s.regional)
            WHERE s.bairro IS NOT NULL
              AND trim(s.bairro) <> ''
            ON CONFLICT DO NOTHING;
            """,
            params_uf if uf_mode == "padrao" else None,
        )

        print("▶ Atualizando dim_local_votacao...", datetime.now())
        executar_sql(
            conn,
            f"""
            INSERT INTO dim_local_votacao (id_municipio, nome, id_bairro)
            SELECT DISTINCT
                m.id_municipio,
                trim(s.local_votacao) AS nome,
                b.id_bairro
            FROM {stg_table} s
            JOIN dim_municipio m
              ON upper(m.nome) = upper(trim(s.municipio))
             AND m.uf = {uf_join}
            LEFT JOIN dim_bairro b
              ON b.id_municipio = m.id_municipio
             AND upper(b.nome) = upper(trim(s.bairro))
            WHERE s.local_votacao IS NOT NULL
              AND trim(s.local_votacao) <> ''
            ON CONFLICT DO NOTHING;
            """,
            params_uf if uf_mode == "padrao" else None,
        )

        print("▶ Atualizando dim_partido...", datetime.now())
        executar_sql(
            conn,
            f"""
            INSERT INTO dim_partido (sigla)
            SELECT DISTINCT trim(s.partido)
            FROM {stg_table} s
            WHERE s.partido IS NOT NULL
              AND trim(s.partido) <> ''
            ON CONFLICT DO NOTHING;
            """,
        )

        print("▶ Atualizando dim_candidato...", datetime.now())
        executar_sql(
            conn,
            f"""
            INSERT INTO dim_candidato (nome, id_partido, id_eleicao, id_municipio)
            SELECT DISTINCT
                trim(s.candidato) AS nome,
                p.id_partido,
                e.id_eleicao,
                m.id_municipio
            FROM {stg_table} s
            JOIN dim_partido p
              ON p.sigla = trim(s.partido)
            JOIN dim_eleicao e
              ON e.ano = s.ano
             AND e.tipo = %s
             AND e.turno = s.turno
             AND e.cargo = trim(s.cargo)
            JOIN dim_municipio m
              ON upper(m.nome) = upper(trim(s.municipio))
             AND m.uf = {uf_join}
            WHERE s.candidato IS NOT NULL
              AND trim(s.candidato) <> ''
            ON CONFLICT DO NOTHING;
            """,
            (tipo_eleicao, *params_uf) if uf_mode == "padrao" else (tipo_eleicao,),
        )

        print("▶ Atualizando fato_votos_local...", datetime.now())
        executar_sql(
            conn,
            f"""
            INSERT INTO fato_votos_local (
                id_eleicao,
                id_municipio,
                id_candidato,
                id_local,
                votos
            )
            SELECT
                e.id_eleicao,
                m.id_municipio,
                c.id_candidato,
                l.id_local,
                SUM(COALESCE(s.votos, 0)) AS votos
            FROM {stg_table} s
            JOIN dim_eleicao e
              ON e.ano = s.ano
             AND e.tipo = %s
             AND e.turno = s.turno
             AND e.cargo = trim(s.cargo)
            JOIN dim_municipio m
              ON upper(m.nome) = upper(trim(s.municipio))
             AND m.uf = {uf_join}
            JOIN dim_partido p
              ON p.sigla = trim(s.partido)
            JOIN dim_candidato c
              ON upper(c.nome) = upper(trim(s.candidato))
             AND c.id_partido = p.id_partido
             AND c.id_eleicao = e.id_eleicao
             AND c.id_municipio = m.id_municipio
            JOIN dim_local_votacao l
              ON upper(l.nome) = upper(trim(s.local_votacao))
             AND l.id_municipio = m.id_municipio
            GROUP BY
                e.id_eleicao,
                m.id_municipio,
                c.id_candidato,
                l.id_local
            ON CONFLICT (id_eleicao, id_municipio, id_candidato, id_local)
            DO UPDATE SET votos = EXCLUDED.votos;
            """,
            (tipo_eleicao, *params_uf) if uf_mode == "padrao" else (tipo_eleicao,),
        )

        conn.commit()

    print(f"✅ Dimensões + fato atualizadas a partir de {stg_table} (tipo={tipo_eleicao}, uf_mode={uf_mode}).", datetime.now())


# =========================
# REFRESH MV
# =========================
def refresh_materialized_view():
    print("▶ Recriando dados da materialized view...")
    with conectar() as conn:
        executar_sql(conn, "REFRESH MATERIALIZED VIEW mv_ranking_candidato;")
        conn.commit()

    garantir_indices_mv()
    print("✅ Materialized view atualizada.")


# =========================
# MAIN
# =========================
def main():
    garantir_estrutura()

    if ETL_MODE in ("municipal", "ambos"):
        if not CSV_MUNICIPAL:
            raise ValueError("CSV_CAMINHO não definido no .env para carga municipal.")

        print("▶ Carregando staging municipal...", datetime.now())
        carregar_csv_para_staging(
            tabela="stg_votos_municipio",
            colunas=[
                "ano",
                "turno",
                "cargo",
                "municipio",
                "candidato",
                "partido",
                "votos",
                "local_votacao",
                "bairro",
                "regional",
            ],
            csv_path=Path(CSV_MUNICIPAL),
        )

        print("▶ Populando dimensões e fato (municipal)...", datetime.now())
        popular_dimensoes_e_fato(
            stg_table="stg_votos_municipio",
            tipo_eleicao=TIPO_ELEICAO_MUNICIPAL,
            uf_mode="padrao",
        )

    if ETL_MODE in ("estadual", "ambos"):
        if not CSV_ESTADUAL:
            raise ValueError("CSV_CAMINHO_ESTADUAL não definido no .env para carga estadual.")

        print("▶ Carregando staging estadual...", datetime.now())
        print(f"▶ CSV_ESTADUAL: {CSV_ESTADUAL}")
        print(f"▶ ETL_MODE: {ETL_MODE} | TIPO_ELEICAO_ESTADUAL: {TIPO_ELEICAO_ESTADUAL}")

        carregar_csv_para_staging(
            tabela="stg_votos_estaduais",
            colunas=[
                "ano",
                "turno",
                "cargo",
                "municipio",
                "candidato",
                "partido",
                "votos",
                "local_votacao",
                "bairro",
                "regional",
                "uf",
            ],
            csv_path=Path(CSV_ESTADUAL),
        )

        print("▶ Populando dimensões e fato (estadual)...", datetime.now())
        popular_dimensoes_e_fato(
            stg_table="stg_votos_estaduais",
            tipo_eleicao=TIPO_ELEICAO_ESTADUAL,
            uf_mode="coluna",
        )

    print("▶ Atualizando materialized view...", datetime.now())
    refresh_materialized_view()

    print("▶ Limpando tabelas de staging...")
    with conectar() as conn:
        executar_sql(conn, "TRUNCATE TABLE stg_votos_estaduais;")
        executar_sql(conn, "TRUNCATE TABLE stg_votos_municipio;")
        conn.commit()

    print("✔ Staging limpa.")
    print("✅ ETL finalizado com sucesso.", datetime.now())
    return 0


if __name__ == "__main__":
    sys.exit(main())