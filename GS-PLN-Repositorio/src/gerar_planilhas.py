"""Gera as planilhas de avaliação (.xlsx) com fórmulas: STT (dados reais dos CSVs), LLM (30 perguntas) e TTS (3 avaliadores).
Pode ser rodado de novo depois do Colab para incluir os novos resultados.   Uso: python -m src.gerar_planilhas"""
import csv, glob, os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .config import BASE, RESULTADOS

F = "Arial"
CAB = PatternFill("solid", fgColor="1F3A5F")
ENT = PatternFill("solid", fgColor="FFF2CC")      # células para preencher
OUT = os.path.join(BASE, "planilhas")


def _cab(ws, linha, titulos, larguras=None):
    for i, t in enumerate(titulos, 1):
        c = ws.cell(row=linha, column=i, value=t)
        c.font, c.fill = Font(name=F, bold=True, color="FFFFFF"), CAB
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for i, w in enumerate(larguras or [], 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _fonte(ws):
    for row in ws.iter_rows():
        for c in row:
            if c.font.name != F:
                c.font = Font(name=F, bold=c.font.bold, color=c.font.color, size=c.font.size)
            c.alignment = Alignment(wrap_text=True, vertical="top", horizontal=c.alignment.horizontal)


def stt():
    arqs = sorted(f for f in glob.glob(os.path.join(RESULTADOS, "stt_*.csv")) if "vies" not in f)
    arqs = [f for f in arqs if os.path.basename(f).startswith("stt_fw_")] or arqs     # prefere faster-whisper (GPU)
    if not arqs:
        return
    linhas = [r for f in arqs for r in csv.DictReader(open(f, encoding="utf-8"))]
    wb = Workbook()
    ws = wb.active
    ws.title = "Dados"
    _cab(ws, 1, ["Modelo", "Arquivo", "Pessoa", "Condição", "Regravação?", "Duração (s)", "Tempo STT (s)", "WER", "Referência", "Transcrição do modelo"],
         [10, 30, 10, 10, 11, 11, 12, 8, 55, 55])
    for i, r in enumerate(linhas, 2):
        ws.append([r["modelo"], r["arquivo"], r["pessoa"], r["condicao"], "sim" if r["retake"] == "True" else "nao",
                   float(r["duracao_s"]), float(r["tempo_stt_s"]), float(r["wer"]), r["referencia"], r["hipotese"]])
    n = len(linhas) + 1
    for i in range(2, n + 1):
        ws.cell(row=i, column=8).number_format = "0.0%"
    ws.freeze_panes = "A2"
    rs = wb.create_sheet("Resumo")
    modelos = sorted({r["modelo"] for r in linhas}, key=lambda m: ["base", "small", "medium"].index(m) if m in ("base", "small", "medium") else 9)
    pessoas = sorted({r["pessoa"] for r in linhas})
    rs["A1"] = "WER (Word Error Rate) calculado com jiwer sobre o conjunto oficial (regravações excluídas). Fórmulas sobre a aba Dados."
    rs["A1"].font = Font(name=F, italic=True)
    _cab(rs, 3, ["Modelo", "Áudios", "WER médio", "WER limpo", "WER ruído", "Tempo STT médio (s)"], [14, 10, 12, 12, 12, 18])
    for i, m in enumerate(modelos, 4):
        rs.cell(row=i, column=1, value=m)
        base = f"Dados!$A$2:$A${n},$A{i},Dados!$E$2:$E${n},\"nao\""
        rs.cell(row=i, column=2, value=f"=COUNTIFS({base})")
        rs.cell(row=i, column=3, value=f"=AVERAGEIFS(Dados!$H$2:$H${n},{base})")
        rs.cell(row=i, column=4, value=f"=AVERAGEIFS(Dados!$H$2:$H${n},{base},Dados!$D$2:$D${n},\"limpo\")")
        rs.cell(row=i, column=5, value=f"=AVERAGEIFS(Dados!$H$2:$H${n},{base},Dados!$D$2:$D${n},\"ruido\")")
        rs.cell(row=i, column=6, value=f"=AVERAGEIFS(Dados!$G$2:$G${n},{base})")
        for c in (3, 4, 5):
            rs.cell(row=i, column=c).number_format = "0.0%"
        rs.cell(row=i, column=6).number_format = "0.00"
    l0 = 5 + len(modelos)
    _cab(rs, l0, ["Pessoa"] + [f"WER {m}" for m in modelos])
    for j, p in enumerate(pessoas, l0 + 1):
        rs.cell(row=j, column=1, value=p)
        for k, m in enumerate(modelos, 2):
            c = rs.cell(row=j, column=k, value=f"=AVERAGEIFS(Dados!$H$2:$H${n},Dados!$A$2:$A${n},\"{m}\",Dados!$C$2:$C${n},$A{j},Dados!$E$2:$E${n},\"nao\")")
            c.number_format = "0.0%"
    for ws_ in (ws, rs):
        _fonte(ws_)
    os.makedirs(OUT, exist_ok=True)
    wb.save(os.path.join(OUT, "planilha_avaliacao_STT.xlsx"))


def llm():
    try:                                  # mantém os arquivos revisado_llm_*.csv em dia com as respostas mais recentes
        from .reavaliar_llm import reavaliar
        reavaliar(RESULTADOS, RESULTADOS)
    except Exception:
        pass
    perguntas = list(csv.DictReader(open(os.path.join(BASE, "dados", "perguntas_llm.csv"), encoding="utf-8")))
    res = {}
    for f in sorted(glob.glob(os.path.join(RESULTADOS, "llm_*.csv"))):
        rows = list(csv.DictReader(open(f, encoding="utf-8")))
        rev = os.path.join(RESULTADOS, "revisado_" + os.path.basename(f))
        if os.path.exists(rev):
            rows = list(csv.DictReader(open(rev, encoding="utf-8")))
        res[rows[0]["modelo"]] = {r["id"]: r for r in rows}
    modelos = list(res) or ["modelo_A", "modelo_B"]
    wb = Workbook()
    ws = wb.active
    ws.title = "Perguntas"
    cab = ["ID", "Tipo", "Pergunta", "Resposta esperada"]
    for m in modelos:
        cab += [f"Resposta {m}", f"Critério inicial {m} (1/0)", f"Critério revisado {m} (1/0)", f"Manual {m} (1/0)", f"Final {m}"]
    _cab(ws, 1, cab, [5, 12, 40, 40] + [45, 11, 11, 10, 9] * len(modelos))
    for i, p in enumerate(perguntas, 2):
        linha = [int(p["id"]), p["tipo"], p["pergunta"], p["resposta_esperada"]]
        for k, m in enumerate(modelos):
            r = res.get(m, {}).get(p["id"])
            ini, rev, man = get_column_letter(6 + 5 * k), get_column_letter(7 + 5 * k), get_column_letter(8 + 5 * k)
            linha += [r["resposta"] if r else "", int(r["correta_auto"]) if r else None,
                      int(r["correta_revisado"]) if r and r.get("correta_revisado", "") != "" else None, None,
                      f'=IF({man}{i}<>"",{man}{i},IF({rev}{i}<>"",{rev}{i},IF({ini}{i}<>"",{ini}{i},"")))']
        ws.append(linha)
        for k in range(len(modelos)):
            ws.cell(row=i, column=8 + 5 * k).fill = ENT
    ws.freeze_panes = "C2"
    rs = wb.create_sheet("Resumo")
    rs["A1"] = ("Final = nota manual (se preenchida), senão critério revisado, senão critério inicial. 1 = correta, 0 = incorreta. "
                "O critério revisado reavalia as MESMAS respostas com marcadores de recusa mais completos e palavras proibidas contra prazos inventados.")
    rs["A1"].font = Font(name=F, italic=True)
    _cab(rs, 3, ["Modelo", "Tema (15)", "Continuação (5)", "Fora do escopo (5)", "Emergência e limites (5)", "Total (30)"], [24, 14, 16, 18, 22, 12])
    for k, m in enumerate(modelos):
        i = 4 + k
        fin = get_column_letter(9 + 5 * k)
        rs.cell(row=i, column=1, value=m)
        for j, tipo in enumerate(["tema", "continuacao", "fora_escopo", "limite"], 2):
            rs.cell(row=i, column=j, value=f'=IFERROR(SUMIFS(Perguntas!${fin}$2:${fin}$31,Perguntas!$B$2:$B$31,"{tipo}")/COUNTIF(Perguntas!$B$2:$B$31,"{tipo}"),"")').number_format = "0%"
        rs.cell(row=i, column=6, value=f'=IFERROR(SUM(Perguntas!${fin}$2:${fin}$31)/30,"")').number_format = "0%"
    for ws_ in (ws, rs):
        _fonte(ws_)
    wb.save(os.path.join(OUT, "planilha_avaliacao_LLM.xlsx"))


def tts():
    frases = list(csv.DictReader(open(os.path.join(BASE, "dados", "frases_tts.csv"), encoding="utf-8")))
    notas, avaliadores = {}, []
    arq = os.path.join(BASE, "dados", "notas_tts.csv")
    if os.path.exists(arq):
        for r in csv.DictReader(open(arq, encoding="utf-8")):
            if r["avaliador"] not in avaliadores:
                avaliadores.append(r["avaliador"])
            notas[(r["id"], r["avaliador"])] = (int(r["naturalidade"]), int(r["clareza"]))
    n_av = len(avaliadores) or 3
    wb = Workbook()
    ws = wb.active
    ws.title = "Avaliação TTS"
    ws["A1"] = "Notas de 1 (péssimo) a 5 (excelente). Naturalidade: quão parecida com fala humana soa a voz. Clareza: quão fácil é entender cada palavra, número e sigla."
    ws["A1"].font = Font(name=F, bold=True)
    ws["A2"] = ("Avaliadores: " + ", ".join(avaliadores) + ". Células amarelas = notas dadas (podem ser editadas; as médias recalculam)."
                if avaliadores else "Preencha só as células amarelas (3 avaliadores ou mais).")
    ws["A2"].font = Font(name=F, italic=True)
    tit = ["ID", "Texto falado"]
    for k in range(n_av):
        nome = avaliadores[k] if avaliadores else f"Avaliador {k + 1}"
        tit += [f"{nome}: naturalidade", f"{nome}: clareza"]
    tit += ["Média naturalidade", "Média clareza"]
    _cab(ws, 4, tit, [8, 60] + [13, 11] * n_av + [14, 12])
    c_ult = 2 + 2 * n_av
    for i, f in enumerate(frases, 5):
        linha = [f["id"], f["resposta_do_assistente"]]
        for k in range(n_av):
            v = notas.get((f["id"], avaliadores[k])) if avaliadores else None
            linha += [v[0] if v else None, v[1] if v else None]
        nat = ",".join(f"{get_column_letter(3 + 2 * k)}{i}" for k in range(n_av))
        cla = ",".join(f"{get_column_letter(4 + 2 * k)}{i}" for k in range(n_av))
        linha += [f'=IF(COUNT({nat})=0,"",AVERAGE({nat}))', f'=IF(COUNT({cla})=0,"",AVERAGE({cla}))']
        ws.append(linha)
        for c in range(3, c_ult + 1):
            ws.cell(row=i, column=c).fill = ENT
        for c in (c_ult + 1, c_ult + 2):
            ws.cell(row=i, column=c).number_format = "0.00"
    u = 5 + len(frases)
    ws.cell(row=u, column=2, value="MÉDIA POR AVALIADOR E GERAL").font = Font(name=F, bold=True)
    for c in range(3, c_ult + 3):
        col = get_column_letter(c)
        ws.cell(row=u, column=c, value=f'=IF(COUNT({col}5:{col}{u - 1})=0,"",AVERAGE({col}5:{col}{u - 1}))').number_format = "0.00"
    _fonte(ws)
    wb.save(os.path.join(OUT, "planilha_avaliacao_TTS.xlsx"))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    stt(); llm(); tts()
    print("Planilhas em", OUT)
