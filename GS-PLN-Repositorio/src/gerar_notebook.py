"""Gera o notebook do Colab (CitizenTech_Zelador_Colab.ipynb). Uso: python -m src.gerar_notebook"""
import json, os

from .config import BASE


def md(t): return {"cell_type": "markdown", "metadata": {}, "source": t.strip("\n").splitlines(True)}
def code(t): return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": t.strip("\n").splitlines(True)}


C = [
md("""
# Zelador: assistente de voz de zeladoria urbana (CitizenTech, GS 2027 PLN)
**Autor:** Octavio Augusto Ramalho Brandão Pires, RM 555696

Fluxo: microfone → **STT** (faster-whisper) → **LLM** (Qwen2.5 via Ollama, com RAG e memória) → **adaptação para fala** → **TTS** (Piper) → alto-falante.

**Como usar no Colab:** menu *Ambiente de execução → Alterar tipo → GPU T4*, depois *Executar tudo*. Tudo é gratuito e roda no próprio Colab, sem API paga.

> **Aviso LGPD:** voz é dado pessoal. O áudio do cidadão é apagado logo depois de transcrito e nada é enviado a APIs externas.

**Se algo der erro:** *Ambiente de execução → Reiniciar sessão* e rode de novo a partir da seção 0. Na demonstração (seção 7), se a tela mostrar "Erro", o motivo aparece na própria conversa e no log da célula.
"""),
md("## 0. Obter o projeto\nA célula confere a versão do projeto. Se achar uma cópia antiga em `/content`, ela é apagada e a atual é obtida de novo: envie o `.zip` do projeto quando o Colab pedir (ou preencha `REPO_URL` com o link do GitHub depois de enviar esta versão para lá)."),
code("""
import os, shutil, subprocess, sys, zipfile

REPO_URL = ""        # opcional: ex. "https://github.com/seu-usuario/seu-repositorio.git" (só depois de subir esta versão corrigida)
VERSAO = "2.0"       # versão do projeto que este notebook espera (src/__init__.py)
RAIZ = "/content" if os.path.isdir("/content") else os.getcwd()

def versao_de(d):
    try:
        return open(os.path.join(d, "src", "__init__.py"), encoding="utf-8").read().split('__versao__ = "')[1].split('"')[0]
    except Exception:
        return None

def achar_projeto():
    for d in [os.getcwd()] + [os.path.join(RAIZ, x) for x in sorted(os.listdir(RAIZ))]:
        if os.path.isdir(d) and versao_de(d) == VERSAO:
            return os.path.abspath(d)

pasta = achar_projeto()
if pasta is None:
    shutil.rmtree(os.path.join(RAIZ, "projeto"), ignore_errors=True)       # cópia antiga ou incompleta
    if REPO_URL:
        subprocess.run(["git", "clone", REPO_URL, os.path.join(RAIZ, "projeto")], check=True)
    else:
        from google.colab import files
        for nome in files.upload():                                         # escolha o .zip do projeto
            if nome.endswith(".zip"):
                zipfile.ZipFile(nome).extractall(RAIZ)
    pasta = achar_projeto()
if pasta is None:
    raise SystemExit("Não achei o projeto na versão " + VERSAO + ". Envie o .zip corrigido (ou suba esta versão ao GitHub).")

os.chdir(pasta)
for m in [m for m in sys.modules if m == "src" or m.startswith("src.")]:    # esquece módulos antigos já importados
    del sys.modules[m]
print("Pasta do projeto:", os.getcwd(), "| versão", versao_de(pasta))
"""),
md("## 1. Instalação (pip, ffmpeg, Ollama)"),
code("""
!pip install -q -r requirements.txt
!pip install -q nvidia-cublas-cu12 nvidia-cudnn-cu12
!apt-get -qq install -y ffmpeg zstd > /dev/null
!curl -fsSL https://ollama.com/install.sh | sh > /dev/null 2>&1

import importlib.metadata as md, subprocess, sys, time, urllib.request

def ollama_ativo():
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2); return True
    except Exception:
        return False

if not ollama_ativo():
    subprocess.Popen(["ollama", "serve"], stdout=open("/tmp/ollama.log", "w"), stderr=subprocess.STDOUT)
    for _ in range(30):
        if ollama_ativo(): break
        time.sleep(2)
print("Ollama no ar" if ollama_ativo() else "Falha ao iniciar o Ollama: " + open("/tmp/ollama.log").read())

for pkg in ("av", "faster-whisper", "ctranslate2", "gradio", "piper-tts"):
    try: print(f"{pkg:15s}", md.version(pkg))
    except md.PackageNotFoundError: print(f"{pkg:15s} NÃO INSTALADO")
if "av" in sys.modules and sys.modules["av"].__version__ != md.version("av"):
    print("ATENÇÃO: o pacote av foi trocado com a sessão aberta. Reinicie a sessão (Ambiente de execução → Reiniciar sessão) e rode de novo a partir da seção 0.")
"""),
code("""
# Modelos do LLM (comparação do LLM: 7B x 3B) e voz do TTS
!ollama pull qwen2.5:7b
!ollama pull qwen2.5:3b
from src.tts import baixar_voz
baixar_voz()
import os; print(os.listdir("modelos/piper"))
"""),
md("## 2. Teste rápido de cada módulo"),
code("""
from src.fala import adaptar_para_fala
print(adaptar_para_fala("**Claro!** Ligue 156 ou use o app SP156. Seu protocolo é ZU-20261112-0001, CEP 01301-000. 😊"))
"""),
code("""
from src.config import KB_DIR
from src.rag import BaseConhecimento
kb = BaseConhecimento(KB_DIR, 5, 0.12)
print(len(kb.chunks), "trechos na base de conhecimento")
for s, c in kb.recuperar("Como peço o conserto de um buraco?")[:3]: print(round(s, 2), c["texto"][:110])
"""),
code("""
from src.pipeline import Assistente
from src.stt import STT; from src.tts import TTS
from src.llm import OllamaChat; from src.dialogo import Dialogo
llm = OllamaChat("qwen2.5:7b"); llm.aquecer()          # carrega o modelo na GPU (a primeira vez demora)
zel = Assistente(STT("faster-whisper", "medium"), Dialogo(llm, kb), TTS(), pasta_audio_saida="/tmp/zel")
r = zel.turno_texto("Oi, quero relatar um buraco enorme na rua Augusta, perto do número quinhentos e vinte.")
print(r["resposta"]); print({k: round(v, 2) for k, v in r.items() if k.endswith("_s")})
from IPython.display import Audio; Audio(r["audio"])
"""),
md("## 3. Avaliação do STT (WER com `jiwer`, 24 áudios, 6 vozes, 6 com ruído) e comparação small × medium"),
code("""
!python -m src.avaliacao_stt --backend faster-whisper --modelos small medium
!python -m src.analise_vies
"""),
md("## 4. Avaliação do LLM (30 perguntas: 15 do tema, 5 de continuação, 5 fora do escopo, 5 de emergência/limites)"),
code("""
!python -m src.avaliacao_llm --modelos qwen2.5:7b qwen2.5:3b
"""),
md("## 5. Avaliação do TTS (10 respostas; as notas de naturalidade e clareza vêm de 3 pessoas)"),
code("""
!python -m src.avaliacao_tts
from IPython.display import Audio, display
import glob, os
for f in sorted(glob.glob("resultados/tts_amostras/*.wav")): print(os.path.basename(f)); display(Audio(f))
"""),
md("## 6. Teste ponta a ponta (10 conversas com 3 ou mais turnos) e latência por etapa"),
code("""
!python -m src.avaliacao_e2e --stt-modelo medium --llm qwen2.5:7b
import pandas as pd
d = pd.read_csv("resultados/e2e_latencia.csv")
print(d[["stt_s", "rag_s", "llm_s", "fala_s", "tts_s", "total_ate_audio_s"]].mean().round(2))
"""),
md("## 7. Demonstração com microfone e upload (Gradio). Use esta célula para gravar o vídeo\nA primeira execução carrega o STT e o LLM na GPU antes de abrir a interface (1 a 3 minutos). Depois, abra o link `gradio.live`, marque o aceite e use o microfone ou envie um áudio."),
code("""
import subprocess, time, urllib.request

def ollama_ativo():
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2); return True
    except Exception:
        return False

if not ollama_ativo():
    subprocess.Popen(["ollama", "serve"], stdout=open("/tmp/ollama.log", "w"), stderr=subprocess.STDOUT)
    for _ in range(30):
        if ollama_ativo(): break
        time.sleep(2)
!ollama pull qwen2.5:7b

from src.app_gradio import criar_app
app = criar_app("faster-whisper", "medium", "qwen2.5:7b")     # carrega e aquece STT e LLM
app.launch(share=True, debug=True)
"""),
md("## 8. Gerar planilhas e relatório com os números reais e baixar tudo"),
code("""
!python -m src.gerar_planilhas
!python -m src.gerar_relatorio
!zip -r -q resultados_colab.zip resultados planilhas relatorio_zelador.pdf
from google.colab import files; files.download("resultados_colab.zip")
"""),
]
nb = {"cells": C, "metadata": {"accelerator": "GPU", "colab": {"provenance": [], "gpuType": "T4"},
      "kernelspec": {"display_name": "Python 3", "name": "python3"}, "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 4}
if __name__ == "__main__":
    with open(os.path.join(BASE, "CitizenTech_Zelador_Colab.ipynb"), "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print("notebook gerado")
