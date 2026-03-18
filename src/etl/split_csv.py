from pathlib import Path
import csv
import math

# caminho do csv original
ARQUIVO_ORIGEM = Path(r"C:\Governix\Dados_Unificados\votacao_secao_2022_CE_tratada.csv")

# pasta de saída
PASTA_SAIDA = ARQUIVO_ORIGEM.parent / "partes_csv"
PASTA_SAIDA.mkdir(exist_ok=True)

NUM_PARTES = 5

with open(ARQUIVO_ORIGEM, "r", encoding="utf-8", newline="") as f:
    reader = csv.reader(f)
    header = next(reader)
    linhas = list(reader)

total_linhas = len(linhas)
linhas_por_parte = math.ceil(total_linhas / NUM_PARTES)

for i in range(NUM_PARTES):
    inicio = i * linhas_por_parte
    fim = inicio + linhas_por_parte
    parte = linhas[inicio:fim]

    arquivo_saida = PASTA_SAIDA / f"{ARQUIVO_ORIGEM.stem}_parte_{i+1}.csv"

    with open(arquivo_saida, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(header)
        writer.writerows(parte)

    print(f"Arquivo criado: {arquivo_saida} | {len(parte)} linhas")

print("✅ Divisão concluída.")