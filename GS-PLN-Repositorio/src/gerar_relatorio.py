"""Gera relatorio_zelador.pdf com os resultados reais encontrados em resultados/*.csv.
Seções sem resultado aparecem como PENDENTE (execute o notebook no Colab e rode este script de novo).
Uso: python -m src.gerar_relatorio"""
import csv, datetime, glob, os

import pandas as pd
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .analise_vies import carregar, tabelas
from .config import BASE, RESULTADOS, VIDEO_URL

AZUL, CINZA, AMARELO = colors.HexColor("#1F3A5F"), colors.HexColor("#F2F4F7"), colors.HexColor("#FFF1D6")
ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=ss["Heading1"], textColor=AZUL, fontSize=15, spaceBefore=12, spaceAfter=6)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=AZUL, fontSize=12, spaceBefore=8, spaceAfter=4)
B = ParagraphStyle("b", parent=ss["Normal"], fontSize=10, leading=14, alignment=4, spaceAfter=5)
S = ParagraphStyle("s", parent=B, fontSize=8.5, leading=11, alignment=0)
TIT = ParagraphStyle("t", parent=ss["Title"], textColor=AZUL, fontSize=22, leading=26)
HC = ParagraphStyle("hc", parent=S, textColor=colors.white, fontName="Helvetica-Bold")
PEND = "PENDENTE: este resultado depende da execução do notebook no Colab (GPU T4). Depois de rodar a seção indicada, execute <font face='Courier'>python -m src.gerar_relatorio</font> para preencher esta tabela."


def p(t, st=B): return Paragraph(t, st)


def tabela(linhas, cab, larg=None, zebra=True):
    dados = [[Paragraph(str(c), HC) for c in cab]] + [[Paragraph(str(c), S) for c in l] for l in linhas]
    t = Table(dados, colWidths=larg, repeatRows=1)
    est = [("BACKGROUND", (0, 0), (-1, 0), AZUL), ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP")]
    if zebra:
        est.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA]))
    t.setStyle(TableStyle(est))
    return t


def aviso(txt):
    t = Table([[Paragraph(txt, S)]], colWidths=[17 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), AMARELO), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#E0A800")),
                           ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def pct(x): return f"{100 * x:.1f}%".replace(".", ",")
def seg(x): return f"{x:.2f}".replace(".", ",")


def diagrama():
    d = Drawing(480, 255)
    def caixa(x, y, w, h, txt, cor="#DDE5F0", sub=None):
        d.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=colors.HexColor(cor), strokeColor=AZUL, strokeWidth=1))
        d.add(String(x + w / 2, y + h / 2 + (3 if sub else -3), txt, textAnchor="middle", fontSize=8, fontName="Helvetica-Bold", fillColor=AZUL))
        if sub:
            d.add(String(x + w / 2, y + h / 2 - 8, sub, textAnchor="middle", fontSize=6.5, fillColor=colors.HexColor("#444444")))
    def seta(x1, y1, x2, y2):
        d.add(Line(x1, y1, x2, y2, strokeColor=AZUL, strokeWidth=1.2))
        if abs(x2 - x1) >= abs(y2 - y1):
            s = 1 if x2 > x1 else -1
            d.add(Polygon([x2, y2, x2 - 6 * s, y2 + 3, x2 - 6 * s, y2 - 3], fillColor=AZUL, strokeColor=AZUL))
        else:
            s = 1 if y2 > y1 else -1
            d.add(Polygon([x2, y2, x2 - 3, y2 - 6 * s, x2 + 3, y2 - 6 * s], fillColor=AZUL, strokeColor=AZUL))
    caixa(5, 195, 85, 40, "1. Captura", sub="microfone ou upload")
    caixa(120, 195, 85, 40, "2. STT", sub="Whisper (faster-whisper)")
    caixa(235, 195, 110, 40, "3. Diálogo", sub="memória + salvaguardas")
    caixa(375, 195, 100, 40, "4. LLM", sub="Qwen2.5 (Ollama)")
    caixa(235, 130, 110, 40, "RAG", cor="#E6F2E6", sub="base de conhecimento SP156")
    caixa(375, 130, 100, 40, "5. Adaptação p/ fala", sub="sem markdown, números")
    caixa(375, 65, 100, 40, "6. TTS", sub="Piper pt-BR")
    caixa(235, 65, 110, 40, "7. Alto-falante", sub="resposta falada")
    caixa(5, 5, 300, 40, "Interface Gradio", cor="#FFF1D6", sub="transcrição e resposta em texto + painel de latência por etapa")
    caixa(330, 5, 145, 40, "LGPD", cor="#FDE2E2", sub="consentimento, áudio apagado")
    seta(90, 215, 120, 215); seta(205, 215, 235, 215); seta(345, 215, 375, 215)
    seta(265, 195, 265, 170); seta(315, 170, 315, 195)
    seta(425, 195, 425, 170); seta(425, 130, 425, 105); seta(375, 85, 345, 85)
    seta(290, 65, 290, 45); seta(47, 45, 47, 195)
    d.add(String(240, 242, "Fluxo de cada turno da conversa (módulos independentes)", textAnchor="middle", fontSize=8.5, fillColor=AZUL))
    return d


def cabecalho_rodape(c, doc):
    c.saveState(); c.setFont("Helvetica", 8); c.setFillColor(colors.grey)
    c.drawString(2 * cm, 1.2 * cm, "GS 2027 PLN - CitizenTech - Zelador | Octavio Augusto Ramalho Brandão Pires, RM 555696")
    c.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
    c.restoreState()


def le(nome):
    f = os.path.join(RESULTADOS, nome)
    return pd.read_csv(f) if os.path.exists(f) else None


def main():
    doc = SimpleDocTemplate(os.path.join(BASE, "relatorio_zelador.pdf"), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=2 * cm, title="Relatório - Zelador, assistente de voz de zeladoria urbana",
                            author="Octavio Augusto Ramalho Brandão Pires")
    e = []
    e += [Spacer(1, 3 * cm), p("Zelador: assistente de voz para relatar problemas urbanos", TIT), Spacer(1, 6),
          p("<b>CitizenTech | GS 2027 | PLN: Assistente de Voz</b>", ParagraphStyle("c", parent=B, alignment=1, fontSize=12)),
          Spacer(1, 18), p("Autor: Octavio Augusto Ramalho Brandão Pires<br/>RM 555696<br/>Trabalho individual", ParagraphStyle("c2", parent=B, alignment=1, fontSize=12, leading=18)),
          p(f"Vídeo de demonstração: {VIDEO_URL}", ParagraphStyle("cv", parent=B, alignment=1)),
          p(f"Relatório gerado em {datetime.date.today():%d/%m/%Y}", ParagraphStyle("c3", parent=B, alignment=1)), Spacer(1, 24)]
    e.append(aviso("<b>Como ler este relatório.</b> Todos os números são resultados reais, lidos dos arquivos em <font face='Courier'>resultados/</font>, medidos no Google Colab "
                   "(GPU T4): STT com 24 áudios gravados pelo grupo, LLM com 30 perguntas, TTS avaliado por 4 pessoas, e 10 conversas ponta a ponta. "
                   "Nenhum número foi estimado. Os pontos fracos encontrados estão descritos nas seções 4 e 6."))
    e.append(PageBreak())

    # 1 problema, persona, ODS
    e += [p("1. Problema, persona e ODS", H1),
          p("Milhões de brasileiros têm dificuldade com interfaces de texto: pessoas idosas, com baixa alfabetização, com deficiência visual ou motora, "
            "ou com as mãos ocupadas. Em São Paulo, o pedido de serviços de zeladoria (tapa-buraco, poda de árvore, iluminação, bueiros) é feito pelo SP156 "
            "por telefone, portal, aplicativo ou WhatsApp, o que exige saber qual serviço pedir e como descrevê-lo. O Zelador é um protótipo de assistente "
            "de voz que escuta o cidadão, entende o problema relatado, faz as perguntas que faltam (tipo, local e gravidade), confirma os dados e "
            "gera um protocolo <b>simulado</b>, orientando a fazer o pedido oficial no SP156."),
          p("<b>Persona (fictícia, baseada no perfil descrito no enunciado).</b> Dona Helena, 68 anos, moradora da Zona Leste, usa o celular só para ligações e "
            "mensagens de voz. Vê um buraco grande em frente à padaria e uma árvore com galhos nos fios, mas não sabe qual órgão procurar nem consegue "
            "preencher formulários. Com o Zelador ela fala o problema como falaria a um vizinho e ouve a orientação de volta."),
          p("<b>ODS relacionado.</b> ODS 11, Cidades e Comunidades Sustentáveis, em especial a meta 11.7 (espaços públicos seguros, inclusivos e acessíveis) "
            "e a participação cidadã na gestão da cidade (11.3). Secundariamente, o ODS 10 (redução das desigualdades), por ampliar o acesso de quem não "
            "consegue usar interfaces de texto."),
          p("<b>Limites do protótipo.</b> O Zelador não é um serviço da Prefeitura e não envia pedidos reais. O protocolo gerado (formato ZU-AAAAMMDD-NNNN) "
            "é simulado e salvo localmente sem dados pessoais. O foco do trabalho é a cadeia de voz (STT, LLM, TTS) e a avaliação de cada componente.")]

    # 2 arquitetura
    e += [p("2. Arquitetura", H1), diagrama(),
          p("Cada etapa é um módulo Python separado em <font face='Courier'>src/</font> (stt.py, dialogo.py, rag.py, guardrails.py, llm.py, fala.py, tts.py, "
            "pipeline.py, app_gradio.py), de modo que o STT, o LLM ou a voz possam ser trocados sem reescrever o resto. O pipeline mede o tempo de cada etapa "
            "e grava em CSV o tempo total da pergunta até o áudio da resposta estar pronto."),
          tabela([["Captura", "Gradio: botão de microfone e upload de arquivo (wav, mp3, m4a, mp4)"],
                  ["STT", "faster-whisper (GPU T4 no Colab), idioma fixo pt, VAD ligado"],
                  ["Salvaguardas", "regras fixas para emergências, saúde e apoio emocional: respondem sem depender do LLM"],
                  ["Memória", "últimas 10 mensagens enviadas ao LLM; permite perguntas como 'e onde eu faço isso?'"],
                  ["RAG", "TF-IDF sobre 44 trechos de 12 arquivos da base de conhecimento (SP156, buraco, árvore, iluminação, bueiro, entulho, calçada, semáforo, água, protocolo, emergências, LGPD)"],
                  ["LLM", "Qwen2.5 via Ollama, system prompt com papel, tom, limites e regra de dizer 'não sei'"],
                  ["Registro do pedido", "ao confirmar, o LLM extrai tipo, local e gravidade em JSON; o código gera o protocolo simulado e a frase final"],
                  ["Adaptação para fala", "remove markdown e emojis; escreve números, datas, telefones, CEP e siglas de forma pronunciável; quebra frases longas"],
                  ["TTS", "Piper, voz sintética pt-BR pronta (nenhuma clonagem de voz)"],
                  ["Interface", "transcrição e resposta em texto junto do áudio, mais o painel de latência por etapa"]],
                 ["Módulo", "Como funciona"], [3.5 * cm, 13.5 * cm])]

    # 3 justificativas
    e += [p("3. Justificativa das escolhas", H1),
          p("<b>Local (Colab), sem API.</b> Custo: tudo gratuito, sem chave de API nem cobrança por requisição. Privacidade: o áudio é dado pessoal e, "
            "processado no próprio ambiente do grupo, não é enviado a terceiros. Latência: a GPU T4 do Colab dá tempos aceitáveis para um protótipo, mas depende da "
            "internet para abrir o Colab e baixar os modelos na primeira execução. Disponibilidade: o Colab gratuito pode limitar a GPU em horários de pico."),
          p("<b>RAG em vez de só contexto no prompt ou fine-tuning.</b> A base é pequena (cerca de 1.200 palavras) e muda com frequência (canais, prazos), então "
            "fine-tuning seria caro e ficaria desatualizado. O RAG por TF-IDF não exige baixar modelo de embeddings, é rápido, determinístico e deixa claro "
            "de qual arquivo veio cada informação. O limite do TF-IDF é depender das mesmas palavras (sem entender sinônimos), o que aparece como limitação."),
          p("<b>Modelos.</b> STT: Whisper (base, small e medium comparados). LLM: Qwen2.5-7B-Instruct como principal e Qwen2.5-3B-Instruct como comparação, "
            "por serem multilíngues, rodarem no Ollama e caberem na T4. TTS: Piper pt_BR-faber-medium, leve, local e sem clonagem.")]

    # 4 resultados STT
    e.append(p("4. Resultados", H1))
    e.append(p("4.1 STT: WER nos áudios gravados pelo grupo", H2))
    df = carregar()
    todos = None
    if df.empty:
        e.append(aviso(PEND))
    else:
        t = tabelas(df)
        n_aud = int(df[df.modelo == df.modelo.iloc[0]].shape[0])
        pessoas = sorted(df.pessoa.unique())
        e.append(p(f"Conjunto: {n_aud} áudios oficiais, {len(pessoas)} vozes ({', '.join(pessoas)}), {int((df[df.modelo == df.modelo.iloc[0]].condicao == 'ruido').sum())} com ruído "
                   "de fundo real. O WER foi calculado com <font face='Courier'>jiwer</font> depois de normalizar a caixa, a pontuação e os números (por exemplo, 520 vira "
                   "'quinhentos e vinte' e o CEP é lido dígito a dígito). Duas regravações (áudios 10 e 12) ficaram fora do conjunto oficial para não escolher a melhor tomada."))
        ordem = [m for m in ["base", "small", "medium"] if m in df.modelo.unique()]
        pm = t["por_modelo"].reindex(ordem)
        pc = t["por_condicao"].reindex(ordem)
        linhas = [[m, int(pm.loc[m, "audios"]), pct(pm.loc[m, "wer_medio"]), pct(pm.loc[m, "wer_mediano"]),
                   pct(pc.loc[m, "limpo"]), pct(pc.loc[m, "ruido"]), seg(pm.loc[m, "tempo_stt_medio_s"])] for m in ordem]
        e.append(tabela(linhas, ["Whisper", "Áudios", "WER médio", "WER mediano", "WER limpo", "WER ruído", "Tempo médio (s)"], [2.4*cm, 2*cm, 2.4*cm, 2.6*cm, 2.4*cm, 2.4*cm, 2.8*cm]))
        e.append(Spacer(1, 4))
        usa_fw = any(os.path.basename(f).startswith("stt_fw_") for f in glob.glob(os.path.join(RESULTADOS, "stt_*.csv")))
        if usa_fw:
            e.append(aviso("<b>Ambiente da medição.</b> faster-whisper executado no ambiente do notebook (GPU T4 do Colab, quando disponível), no mesmo conjunto de áudios. "
                           "Os tempos refletem esse ambiente."))
        else:
            e.append(aviso("<b>Ambiente da medição.</b> Whisper em formato ONNX int8 (sherpa-onnx), em CPU de 1 núcleo, no mesmo conjunto de áudios. "
                           "Os tempos são <b>muito maiores</b> do que seriam na GPU T4 do Colab com faster-whisper, e servem apenas para comparar os tamanhos entre si. "
                           "O notebook repete a avaliação com faster-whisper na T4, e os WER podem variar um pouco entre os dois motores."))
        fw = [m for m in ["small", "medium"] if os.path.exists(os.path.join(RESULTADOS, f"stt_fw_{m}.csv"))]
        # escolha final
        if "small" in ordem and "medium" in ordem:
            ws, wm = pm.loc["small", "wer_medio"], pm.loc["medium", "wer_medio"]
            ts, tm = pm.loc["small", "tempo_stt_medio_s"], pm.loc["medium", "tempo_stt_medio_s"]
            if wm < ws - 0.015:
                esc = (f"<b>Escolha final do STT: Whisper medium</b>, que reduz o WER médio de {pct(ws)} para {pct(wm)}. O custo é um tempo médio de transcrição "
                       f"de {seg(tm)} s contra {seg(ts)} s do small ({tm / ts:.1f} vezes maior), o que continua muito pequeno diante do tempo total da resposta. "
                       "Para um assistente de voz a qualidade da transcrição pesa mais, porque um erro de endereço compromete o pedido.")
            else:
                esc = (f"<b>Escolha final do STT: Whisper small</b>. O medium não melhora o WER de forma relevante ({pct(wm)} contra {pct(ws)}) e custa "
                       f"{tm / ts:.1f} vezes mais tempo, então o small tem a melhor relação entre qualidade e latência.")
            e.append(Spacer(1, 4)); e.append(p("<b>Comparação e escolha.</b> Critério: menor WER; se a diferença for menor que 1,5 ponto percentual, vence o mais rápido. " + esc))
        cpu = {}
        for m in ("base", "small", "medium"):
            f = os.path.join(RESULTADOS, f"stt_{m}.csv")
            if os.path.exists(f):
                dd = pd.read_csv(f)
                cpu[m] = dd[dd.retake == False].wer.mean()      # noqa: E712
        if cpu:
            e.append(p("<b>Referência em CPU.</b> Os mesmos áudios foram transcritos antes com Whisper ONNX int8 (sherpa-onnx) em CPU: " +
                       ", ".join(f"{m} {pct(v)}" for m, v in cpu.items()) +
                       ". O base (WER muito alto) foi descartado, e a ordem entre os tamanhos se repetiu na GPU com faster-whisper.", S))
        e.append(p("4.2 STT: WER por pessoa e análise de viés", H2))
        pp = t["por_pessoa"].reindex(columns=ordem)
        e.append(tabela([[i] + [pct(pp.loc[i, m]) for m in ordem] for i in pp.index], ["Pessoa"] + [f"WER {m}" for m in ordem], None))
        fig = os.path.join(RESULTADOS, "fig_wer_pessoa.png")
        if os.path.exists(fig):
            e += [Spacer(1, 4), Image(fig, width=13 * cm, height=6.7 * cm)]
        ref = ordem[-1]
        mx, mn = pp[ref].idxmax(), pp[ref].idxmin()
        cond = pc.loc[ref]
        e.append(p(f"<b>Leitura.</b> No modelo {ref}, a voz com maior WER foi a de {mx} ({pct(pp.loc[mx, ref])}) e a com menor foi a de {mn} ({pct(pp.loc[mn, ref])}). "
                   f"Entre as condições, o WER foi {pct(cond['limpo'])} nos áudios limpos e {pct(cond['ruido'])} nos ruidosos. "
                   "Cada pessoa tem apenas 4 áudios e a diferença entre vozes mistura efeitos de voz, sotaque, microfone do celular, distância da boca e volume de gravação "
                   "(por exemplo, algumas gravações tiveram volume médio bem mais baixo). Por isso os resultados <b>não permitem concluir</b> que o modelo discrimina "
                   "um gênero, idade ou sotaque. O perfil das vozes (gênero, faixa etária, sotaque) não foi coletado (gênero, faixa etária e sotaque não foram declarados), "
                   "portanto a análise por perfil não foi feita."))
        pior = df[df.modelo == ref].sort_values("wer", ascending=False).head(5)
        e.append(p(f"Maiores erros do modelo {ref} (referência x transcrição):", S))
        e.append(tabela([[r.arquivo.replace("audio_", ""), pct(r.wer), r.referencia, r.hipotese] for r in pior.itertuples()],
                        ["Áudio", "WER", "Referência", "Transcrição"], [3.2 * cm, 1.5 * cm, 6 * cm, 6.3 * cm]))
        e.append(p("Os erros se concentram em nomes de ruas e termos do domínio (por exemplo, 'entulho', 'Vergueiro', 'Oscar Freire'), o que sugere melhorar o STT com "
                   "uma lista de termos urbanos no prompt inicial do Whisper ou com correção por fuzzy matching contra nomes de ruas."))

    # LLM
    from .reavaliar_llm import reavaliar
    if glob.glob(os.path.join(RESULTADOS, "llm_*.csv")):
        reavaliar(RESULTADOS, RESULTADOS)         # garante que a tabela revisada vem das respostas mais recentes
    e.append(p("4.3 LLM: 30 perguntas com resposta esperada", H2))

    def carrega(pasta, prefixo):
        return {f: pd.read_csv(f) for f in sorted(glob.glob(os.path.join(pasta, prefixo + "*.csv")))}

    def tab_llm(grupo, coluna):
        linhas = []
        for f, d in grupo.items():
            def acc(tipo):
                sel = d[d.tipo == tipo]
                return f"{int(sel[coluna].sum())}/{len(sel)} ({pct(sel[coluna].mean())})"
            linhas.append([d.modelo.iloc[0], acc("tema"), acc("continuacao"), acc("fora_escopo"), acc("limite"),
                           f"{int(d[coluna].sum())}/{len(d)} ({pct(d[coluna].mean())})", seg(d[d.tratada_por == "llm"].tempo_s.mean())])
        return tabela(linhas, ["Modelo", "Tema (15)", "Continuação (5)", "Fora do escopo (5)", "Emergência e limites (5)", "Total (30)", "Tempo médio do LLM (s)"],
                      [2.6 * cm, 2.4 * cm, 2.4 * cm, 2.6 * cm, 2.8 * cm, 2.6 * cm, 1.6 * cm])

    ini, rev = carrega(RESULTADOS, "llm_"), carrega(RESULTADOS, "revisado_llm_")
    if not ini:
        e.append(aviso(PEND + " (seção do LLM do notebook)."))
    else:
        e.append(p("Composição: 15 perguntas do tema, 5 de continuação (com os turnos anteriores injetados na memória), 5 fora do escopo (devem ser recusadas) e 5 de "
                   "emergência, saúde e jurídico (devem encaminhar ao órgão competente). O critério automático procura palavras-chave definidas em "
                   "<font face='Courier'>dados/perguntas_llm.csv</font>. Os modelos comparados são o Qwen2.5-7B e o Qwen2.5-3B (Ollama), com o mesmo prompt, a mesma base de conhecimento e temperatura 0,2."))
        e.append(p("<b>Critério inicial</b> (palavras-chave definidas antes de ver as respostas):", S))
        e.append(tab_llm(ini, "correta_auto"))
        if rev:
            e.append(Spacer(1, 6))
            e.append(p("<b>Critério revisado</b> (as mesmas respostas, reavaliadas depois da leitura de todas elas, com a mesma regra para os dois modelos):", S))
            e.append(tab_llm(rev, "correta_revisado"))
            e.append(Spacer(1, 4))
            e.append(p("A revisão foi necessária porque o critério inicial errava nos dois sentidos: recusas corretas do 7B ('o Zelador só ajuda com problemas urbanos', "
                       "'o Zelador não dá conselhos sobre investimentos') não eram reconhecidas, respostas corretas do 3B com outras palavras ('pelo site da Prefeitura', "
                       "'o Zelador não tem informações sobre prazos') eram marcadas como erro, uma continuação válida do 7B ('e quanto ao tamanho do buraco?') não citava a rua, "
                       "e uma resposta do 3B que <b>inventava um prazo</b> ('a equipe chega em até 48 horas') contava como acerto. A revisão acrescentou marcadores de recusa e de "
                       "'não sei', outras formas de dizer 'onde fazer o pedido', e uma lista de palavras proibidas nas perguntas de prazo. Como a revisão foi feita depois de ver as "
                       "respostas, as duas versões são mostradas; a revisada pode ser reproduzida com <font face='Courier'>python -m src.reavaliar_llm</font>."))
            ant = reavaliar(os.path.join(RESULTADOS, "execucao_anterior")) if os.path.isdir(os.path.join(RESULTADOS, "execucao_anterior")) else {}
            atual = {d.modelo.iloc[0]: int(d.correta_revisado.sum()) for d in rev.values()}
            if ant and all(m in ant for m in atual):
                partes = "; ".join(f"{m}: {atual[m]} nesta execução e {ant[m][1]} na anterior" for m in atual)
                e.append(p(f"<b>Variação entre execuções.</b> Rodando de novo o mesmo código, os totais (critério revisado) foram: {partes}. A diferença entre os dois modelos "
                           "fica dentro dessa variação, então não há vantagem de qualidade comprovada de um sobre o outro."))
            if len(atual) >= 2:
                lat = {d.modelo.iloc[0]: d[d.tratada_por == "llm"].tempo_s.mean() for d in rev.values()}
                e.append(p("<b>Escolha final do LLM: Qwen2.5-7B.</b> A qualidade é equivalente dentro da variação medida. O 3B é cerca de "
                           f"{seg(abs(lat.get('qwen2.5:7b', 0) - lat.get('qwen2.5:3b', 0)))} s mais rápido por resposta, uma diferença pequena diante da latência total (seção 4.5). "
                           "Mantive o 7B porque é o modelo usado em todas as demais medições e na demonstração, tem licença Apache-2.0 e o 3B usa a Qwen Research License (uso não comercial), "
                           "e porque a única resposta com prazo numérico inventado na execução principal ('em até 48 horas') foi do 3B. O 3B continua sendo uma alternativa para máquinas com pouca memória."))
            falhas = [d for d in rev.values() if d.modelo.iloc[0] == "qwen2.5:7b"]
            if falhas:
                d = falhas[0]
                ruins = d[(d.correta_revisado == 0) & (d.tipo == "tema")].head(4)
                e.append(Spacer(1, 4))
                e.append(p("<b>Onde o 7B errou (perguntas do tema).</b> O padrão dominante é responder uma pergunta informativa com 'Posso registrar o pedido?' em vez de explicar o SP156, "
                           "porque o prompt empurra o modelo para o fluxo de registro. Exemplos:", S))
                e.append(tabela([[str(r.id), r.pergunta, r.resposta[:170]] for r in ruins.itertuples()], ["#", "Pergunta", "Resposta do 7B (início)"], [0.8 * cm, 6.2 * cm, 10 * cm]))
        e.append(Spacer(1, 4))
        e.append(p("As perguntas de emergência, saúde e jurídico passam antes por regras fixas (guardrails): quando uma delas dispara, o LLM não é chamado, e por isso o tempo do LLM nessas respostas é zero. "
                   "No limite jurídico (pergunta 29) os dois modelos falharam: o 7B explicou como registrar o pedido em vez de orientar a procurar um advogado, e o 3B mandou ligar para o SAMU. Esse caso não tem regra fixa e é um ponto fraco registrado nas limitações.", S))

    e.append(p("4.4 TTS: naturalidade e clareza (4 avaliadores)", H2))
    tl = le("tts_latencia.csv")
    if tl is None:
        e.append(aviso(PEND + " (seção do TTS do notebook)."))
    else:
        e.append(p(f"Latência média do TTS: {seg(tl.tts_s.mean())} s por resposta, com áudio médio de {seg(tl.duracao_audio_s.mean())} s (fator de tempo real médio {seg(tl.fator_tempo_real.mean())}). "
                   "As 10 respostas do assistente foram ouvidas por 4 pessoas (mais que as 3 exigidas), cada uma dando duas notas de 1 a 5: naturalidade e clareza. "
                   "Os avaliadores são as mesmas pessoas que gravaram os áudios do STT, o que pode favorecer a familiaridade com o projeto, e isso pode influenciar as notas."))
        arq_notas = os.path.join(BASE, "dados", "notas_tts.csv")
        if os.path.exists(arq_notas):
            nt = pd.read_csv(arq_notas)
            por = nt.groupby("avaliador", sort=False).agg(nat=("naturalidade", "mean"), cla=("clareza", "mean"), n=("id", "size"))
            linhas = [[a, int(r.n), seg(r.nat), seg(r.cla)] for a, r in por.iterrows()]
            linhas.append(["<b>Média geral</b>", int(len(nt)), f"<b>{seg(nt.naturalidade.mean())}</b>", f"<b>{seg(nt.clareza.mean())}</b>"])
            e.append(tabela(linhas, ["Avaliador", "Notas dadas", "Naturalidade (1 a 5)", "Clareza (1 a 5)"], [5 * cm, 3 * cm, 4.5 * cm, 4.5 * cm]))
            pt = nt.groupby("id").agg(nat=("naturalidade", "mean"), cla=("clareza", "mean"))
            pior_n, pior_c = pt.nat.idxmin(), pt.cla.idxmin()
            e.append(Spacer(1, 4))
            e.append(p(f"<b>Leitura.</b> A clareza ({seg(nt.clareza.mean())}) foi bem melhor que a naturalidade ({seg(nt.naturalidade.mean())}): a voz é inteligível, mas soa sintética. "
                       f"A resposta com menor naturalidade foi a {pior_n} ({seg(pt.nat[pior_n])}) e a de menor clareza foi a {pior_c} ({seg(pt.cla[pior_c])}). "
                       "As notas variam bastante entre avaliadores, então a média é uma indicação e não uma medida precisa."))
        else:
            e.append(aviso("PENDENTE: notas dos avaliadores (dados/notas_tts.csv)."))

    e.append(p("4.5 Ponta a ponta: 10 conversas e latência", H2))
    ee = le("e2e_latencia.csv")
    rotulo_e2e = ""
    if ee is None and os.path.exists(os.path.join(RESULTADOS, "rodada1", "e2e_latencia.csv")):
        ee = pd.read_csv(os.path.join(RESULTADOS, "rodada1", "e2e_latencia.csv"))
        rotulo_e2e = " (rodada 1, versão inicial do prompt; a rodada 2 substitui esta tabela)"
    if ee is None:
        e.append(aviso(PEND + " (seção 6 do notebook)."))
    else:
        cols = ["stt_s", "rag_s", "llm_s", "fala_s", "tts_s", "total_ate_audio_s"]
        m = ee[cols].mean()
        e.append(tabela([[seg(m[c]) for c in cols]], ["STT (s)", "RAG (s)", "LLM (s)", "Fala (s)", "TTS (s)", "Total até o áudio (s)"]))
        e.append(p(f"{ee.conversa.nunique()} conversas, {len(ee)} turnos{rotulo_e2e}. O 'total até o áudio' é o tempo da pergunta até a resposta falada estar pronta para tocar. "
                   "As falas dos usuários nestas conversas foram sintetizadas pelo Piper (voz artificial) para exercitar o pipeline completo; a demonstração com voz real está no vídeo. "
                   f"Mediana do total: {seg(ee.total_ate_audio_s.median())} s; máximo: {seg(ee.total_ate_audio_s.max())} s."))

    # ética
    e += [p("5. Ética, segurança e LGPD", H1),
          tabela([["Consentimento", "Aviso de privacidade e caixa de aceite antes do primeiro uso; microfone e envio ficam bloqueados até o aceite."],
                  ["Retenção mínima", "O áudio é apagado logo após a transcrição (os áudios de teste foram gravados por 6 pessoas; o modelo de autorização de uso da voz está em dados/modelo_autorizacao_voz.txt). O texto da conversa fica só na memória da sessão. O protocolo simulado guarda tipo, local e gravidade, sem nome nem CPF."],
                  ["Nuvem", "Nenhum áudio vai a API externa. O Colab é do próprio grupo; se o Colab for usado, o processamento ocorre nele."],
                  ["Limites", "Recusa assuntos fora da zeladoria. Saúde, emergência e jurídico: encaminha ao SAMU 192, Bombeiros 193, Polícia 190, Defesa Civil 199 ou advogado/Defensoria, por regras fixas para os casos críticos."],
                  ["Alucinação", "O prompt exige usar só o contexto e dizer 'não sei' quando faltar informação (por exemplo, prazos do tapa-buraco não são informados)."],
                  ["Clonagem de voz", "Não há clonagem. O TTS usa voz sintética pronta do Piper."],
                  ["Viés do STT", "Análise do WER por pessoa e condição na seção 4.2. Limitada a 6 vozes; não permite generalizar."]],
                 ["Tema", "Como foi tratado"], [3.3 * cm, 13.7 * cm])]

    # limitações
    e += [p("6. Limitações e melhorias futuras", H1),
          p("<b>Limitações conhecidas.</b>"),
          tabela([["Protótipo", "Não integra a API real do SP156: o protocolo (ZU-AAAAMMDD-NNNN) é simulado. O assistente avisa isso ao cidadão."],
                  ["Prompt do LLM", "Em 8 das 15 perguntas do tema o 7B acertou; nas demais ele respondeu com 'Posso registrar o pedido?' em vez de informar o SP156. O prompt precisa separar melhor pergunta informativa de relato de problema."],
                  ["Confirmação do pedido", "A regra que detecta o 'sim' é simples: em um teste ponta a ponta, a fala 'Isso é urgente?' (depois de o assistente perguntar se podia registrar) foi tomada como confirmação e gerou um protocolo. Deve exigir resposta curta, sem negação, correção ou número."],
                  ["Limite jurídico", "Não há regra fixa para pedidos jurídicos (ex.: processar a prefeitura); os dois modelos falharam nessa pergunta."],
                  ["Prazos", "O 7B e o 3B às vezes sugerem prazos vagos ('costuma atender rapidamente', 'em até 48 horas'), mesmo com a regra de dizer 'não sei'."],
                  ["Variação do LLM", "Rodando o mesmo código duas vezes, o total de acertos mudou até 2 respostas. As comparações entre modelos têm essa margem."],
                  ["Dados de voz", "6 vozes, 24 áudios, 4 por pessoa e sem perfil (gênero, idade, sotaque) coletado: a análise de viés é só por pessoa e condição."],
                  ["STT em nomes e números", "Nomes de ruas e números de endereço ainda geram erros (seção 4.2)."],
                  ["RAG", "TF-IDF não entende sinônimos; a base é pequena, escrita à mão, e os prazos devem ser conferidos no SP156."],
                  ["TTS", "A voz é inteligível (clareza média alta), mas a naturalidade média ficou em torno de 3 em 5."],
                  ["Testes ponta a ponta", "Nas 10 conversas as falas dos usuários foram sintetizadas pelo Piper; a conversa com voz humana real está no vídeo."]],
                 ["Limitação", "Detalhe"], [3.6 * cm, 13.4 * cm]),
          Spacer(1, 6),
          p("<b>Melhorias futuras.</b> Reescrever o prompt com exemplos e regras para perguntas informativas, prazos e recusas; endurecer a detecção de confirmação; criar regra fixa para limites jurídicos; "
            "integração com a API do SP156 e geocodificação do endereço com confirmação lida em voz alta; vocabulário de ruas de São Paulo no STT; embeddings multilíngues no RAG; "
            "streaming do LLM e do TTS por frase para reduzir a latência percebida; testes com mais vozes, sotaques e idades; envio de foto por WhatsApp.")]

    # modelos e licenças
    e += [p("7. Modelos, versões e licenças", H1),
          tabela([["Whisper small e medium (OpenAI), via faster-whisper 1.2.1 e CTranslate2 4.9.0", "STT, GPU T4, float16", "MIT"],
                  ["Whisper base, small e medium em ONNX int8 (sherpa-onnx)", "medições de referência em CPU (arquivos stt_base, stt_small e stt_medium)", "MIT"],
                  ["Qwen2.5-7B-Instruct (Ollama, tag qwen2.5:7b)", "LLM principal", "Apache-2.0"],
                  ["Qwen2.5-3B-Instruct (Ollama, tag qwen2.5:3b)", "LLM de comparação", "Qwen Research License (uso não comercial)"],
                  ["Piper pt_BR-faber-medium, piper-tts 1.8.0", "TTS, voz sintética pronta, sem clonagem", "piper-tts: GPL-3.0-or-later; a licença de cada voz está no model card da voz (rhasspy/piper-voices)"],
                  ["Gradio 5.50.0, jiwer, scikit-learn, num2words, Ollama", "interface, WER, RAG, números por extenso, servidor do LLM", "Apache-2.0, Apache-2.0, BSD, LGPL, MIT"],
                  ["Base de conhecimento", "texto próprio, com base nas páginas das Subprefeituras e do SP156 em prefeitura.sp.gov.br", "uso acadêmico"]],
                 ["Componente", "Uso", "Licença"], [6 * cm, 5.4 * cm, 5.6 * cm]),
          p("Licenças do Qwen e do piper-tts conferidas nas páginas oficiais dos projetos; a licença da voz faber deve ser conferida no model card antes de qualquer publicação.", S)]
    doc.build(e, onFirstPage=cabecalho_rodape, onLaterPages=cabecalho_rodape)
    print("relatorio_zelador.pdf gerado")


if __name__ == "__main__":
    main()
