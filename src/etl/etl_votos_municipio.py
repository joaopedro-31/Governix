import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import psycopg

# =========================
# CONFIGURAÇÕES
# =========================

load_dotenv()

PG_CONFIG = {
    "host": os.getenv("PGHOST"),
    "port": int(os.getenv("PGPORT")),
    "dbname": os.getenv("PGDATABASE"),
    "user": os.getenv("PGUSER"),
    "password": os.getenv("PGPASSWORD"),
    "sslmode": os.getenv("PGSSLMODE"),
}

CSV_CAMINHO = Path(os.getenv("CSV_CAMINHO"))
UF_PADRAO = os.getenv("UF_PADRAO")
TIPO_ELEICAO = os.getenv("TIPO_ELEICAO")     # usado
# (1) Removi CARGO_PADRAO e TURNO_PADRAO porque não são mais usados

# =========================
# CONEXÃO
# =========================

def conectar():
    return psycopg.connect(**PG_CONFIG)

def executar_sql(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)

def contar_linhas(conn, tabela):
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {tabela};")
        print(f"▶ {tabela}: {cur.fetchone()[0]} linhas")

# =========================
# DDL
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

# =========================
# STAGING
# =========================

def carregar_staging():
    with conectar() as conn:
        executar_sql(conn, "TRUNCATE TABLE stg_votos_municipio;")

        copy_sql = """
            COPY stg_votos_municipio (
                ano, turno, cargo,
                municipio, candidato, partido,
                votos, local_votacao, bairro, regional
            )
            FROM STDIN
            WITH (FORMAT csv, HEADER true, DELIMITER ',', ENCODING 'UTF8');
        """

        with conn.cursor() as cur, open(CSV_CAMINHO, "r", encoding="utf-8") as f:
            with cur.copy(copy_sql) as cp:
                for linha in f:
                    cp.write(linha)

        contar_linhas(conn, "stg_votos_municipio")

# =========================
# DIMENSÕES
# =========================

def popular_dimensoes():
    with conectar() as conn:

        # (2) CORRIGIDO: apenas 1 parâmetro (%s)
        executar_sql(conn, """
            INSERT INTO dim_eleicao (ano, tipo, turno, cargo)
            SELECT DISTINCT
                ano,
                %s AS tipo,
                turno,
                cargo
            FROM stg_votos_municipio
            ON CONFLICT DO NOTHING;
        """, (TIPO_ELEICAO,))

        executar_sql(conn, """
            INSERT INTO dim_municipio (nome, uf)
            SELECT DISTINCT municipio, %s FROM stg_votos_municipio
            ON CONFLICT DO NOTHING;
        """, (UF_PADRAO,))

        executar_sql(conn, """
            INSERT INTO dim_regional (nome)
            SELECT DISTINCT trim(regional)
            FROM stg_votos_municipio
            WHERE regional IS NOT NULL AND trim(regional) <> ''
            ON CONFLICT DO NOTHING;
        """)

        executar_sql(conn, """
            INSERT INTO dim_bairro (id_municipio, nome, id_regional)
            SELECT DISTINCT m.id_municipio, trim(s.bairro), r.id_regional
            FROM stg_votos_municipio s
            JOIN dim_municipio m ON m.nome = s.municipio AND m.uf = %s
            LEFT JOIN dim_regional r ON r.nome = trim(s.regional)
            WHERE s.bairro IS NOT NULL AND trim(s.bairro) <> ''
            ON CONFLICT DO NOTHING;
        """, (UF_PADRAO,))

        executar_sql(conn, """
            INSERT INTO dim_local_votacao (id_municipio, nome, id_bairro)
            SELECT DISTINCT m.id_municipio, trim(s.local_votacao), b.id_bairro
            FROM stg_votos_municipio s
            JOIN dim_municipio m ON m.nome = s.municipio AND m.uf = %s
            LEFT JOIN dim_bairro b
              ON b.nome = trim(s.bairro) AND b.id_municipio = m.id_municipio
            WHERE s.local_votacao IS NOT NULL AND trim(s.local_votacao) <> ''
            ON CONFLICT DO NOTHING;
        """, (UF_PADRAO,))

        executar_sql(conn, """
            INSERT INTO dim_partido (sigla)
            SELECT DISTINCT trim(partido)
            FROM stg_votos_municipio
            WHERE partido IS NOT NULL AND trim(partido) <> ''
            ON CONFLICT DO NOTHING;
        """)

        # (3) CORRIGIDO: apenas os 2 parâmetros necessários
        executar_sql(conn, """
            INSERT INTO dim_candidato (nome, id_partido, id_eleicao, id_municipio)
            SELECT DISTINCT
                trim(s.candidato),
                p.id_partido,
                e.id_eleicao,
                m.id_municipio
            FROM stg_votos_municipio s
            JOIN dim_partido p ON p.sigla = trim(s.partido)
            JOIN dim_eleicao e ON e.ano = s.ano
                              AND e.tipo = %s
                              AND e.turno = s.turno
                              AND e.cargo = s.cargo
            JOIN dim_municipio m ON m.nome = s.municipio AND m.uf = %s
            ON CONFLICT DO NOTHING;
        """, (TIPO_ELEICAO, UF_PADRAO))

# =========================
# FATO EM BLOCOS
# =========================

def popular_fato_em_blocos(batch_size=10000):
    offset = 0

    while True:
        with conectar() as conn:
            with conn.cursor() as cur:

                sql = f"""
                    WITH dados AS (
                        SELECT
                            e.id_eleicao,
                            m.id_municipio,
                            c.id_candidato,
                            l.id_local,
                            SUM(COALESCE(s.votos, 0)) AS votos
                        FROM stg_votos_municipio s
                        JOIN dim_eleicao e
                          ON e.ano = s.ano
                         AND e.tipo = %s
                         AND e.turno = s.turno
                         AND e.cargo = s.cargo
                        JOIN dim_municipio m
                          ON m.nome = s.municipio AND m.uf = %s
                        JOIN dim_partido p
                          ON p.sigla = trim(s.partido)
                        JOIN dim_candidato c
                          ON c.nome = trim(s.candidato)
                         AND c.id_partido = p.id_partido
                         AND c.id_eleicao = e.id_eleicao
                         AND c.id_municipio = m.id_municipio
                        JOIN dim_local_votacao l
                          ON l.nome = trim(s.local_votacao)
                         AND l.id_municipio = m.id_municipio
                        GROUP BY e.id_eleicao, m.id_municipio, c.id_candidato, l.id_local
                        ORDER BY 1,2,3,4
                        LIMIT {batch_size}
                        OFFSET {offset}
                    )
                    INSERT INTO fato_votos_local (
                        id_eleicao, id_municipio, id_candidato, id_local, votos
                    )
                    SELECT * FROM dados
                    ON CONFLICT (id_eleicao, id_municipio, id_candidato, id_local)
                    DO UPDATE SET votos = EXCLUDED.votos;
                """

                # (4) CORRIGIDO: somente os 2 parâmetros usados no JOIN
                cur.execute(sql, (TIPO_ELEICAO, UF_PADRAO))

                linhas = cur.rowcount
                conn.commit()

        if linhas == 0:
            break

        print(f"✔ Bloco carregado: {linhas} linhas")
        offset += batch_size

    print("✅ Carga da fato finalizada.")

# =========================
# MAIN
# =========================

def main():
    print("▶ Criando tabelas...")
    with conectar() as conn:
        executar_sql(conn, DDL_SQL)

    print("▶ Carregando staging...")
    carregar_staging()

    print("▶ Populando dimensões...")
    popular_dimensoes()

    print("▶ Populando fato em blocos...")
    popular_fato_em_blocos()

    print("✅ ETL finalizado com sucesso.")

if __name__ == "__main__":
    sys.exit(main())