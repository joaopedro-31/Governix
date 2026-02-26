import os
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase

load_dotenv()

db_uri = f"postgresql+psycopg://{os.getenv('PGUSER')}:{os.getenv('PGPASSWORD')}@{os.getenv('PGHOST')}:{os.getenv('PGPORT')}/{os.getenv('PGDATABASE')}"
db = SQLDatabase.from_uri(db_uri)

print("--- Tabelas Detectadas no Banco ---")
print(db.get_usable_table_names())

print("\n--- Amostra de Dados (Tabela Fato) ---")
# Troque 'fato_votos_local' pelo nome da sua tabela se for diferente
try:
    print(db.run("SELECT * FROM fato_votos_local LIMIT 3;"))
    print("\n✅ Conexão e leitura bem-sucedidas!")
except Exception as e:
    print(f"\n❌ Erro ao ler: {e}")