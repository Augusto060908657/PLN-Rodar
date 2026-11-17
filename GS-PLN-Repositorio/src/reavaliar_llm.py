"""Reavalia, SEM chamar o LLM de novo, as respostas já salvas em resultados/llm_*.csv com o critério revisado
(dados/perguntas_llm.csv: marcadores de recusa mais completos e lista de palavras proibidas contra prazos inventados).
Gera resultados/revisado_llm_<modelo>.csv (com a coluna correta_revisado) e imprime os totais.
Também reavalia a execução anterior (resultados/execucao_anterior/) para mostrar a variação entre execuções.
Uso: python -m src.reavaliar_llm"""
import csv, glob, os

import pandas as pd

from .config import BASE, RESULTADOS
from .metricas import acerto_palavras_chave


def reavaliar(pasta, saida=None):
    perguntas = {r["id"]: r for r in csv.DictReader(open(os.path.join(BASE, "dados", "perguntas_llm.csv"), encoding="utf-8"))}
    totais = {}
    for f in sorted(glob.glob(os.path.join(pasta, "llm_*.csv"))):
        d = pd.read_csv(f)
        d["correta_revisado"] = [int(acerto_palavras_chave(r.resposta, perguntas[str(r.id)]["palavras_chave"],
                                                          perguntas[str(r.id)].get("proibidas", ""))) for r in d.itertuples()]
        modelo = d.modelo.iloc[0]
        totais[modelo] = (int(d.correta_auto.sum()), int(d.correta_revisado.sum()), len(d))
        if saida:
            d.to_csv(os.path.join(saida, f"revisado_llm_{modelo.replace(':', '_')}.csv"), index=False, encoding="utf-8")
    return totais


if __name__ == "__main__":
    for rotulo, pasta, saida in (("execução principal", RESULTADOS, RESULTADOS),
                                 ("execução anterior", os.path.join(RESULTADOS, "execucao_anterior"), None)):
        if os.path.isdir(pasta):
            for m, (a, r, n) in reavaliar(pasta, saida).items():
                print(f"{rotulo} | {m}: critério inicial {a}/{n}, critério revisado {r}/{n}")
