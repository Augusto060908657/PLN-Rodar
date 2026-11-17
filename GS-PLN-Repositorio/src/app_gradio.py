"""Interface Gradio: consentimento, microfone (apertar para falar) e upload, transcrição + resposta em texto,
áudio da resposta e painel de latência.
Uso local:  python -m src.app_gradio [--share] [--stt-modelo small] [--llm qwen2.5:3b]"""
import argparse, os, tempfile, traceback

import gradio as gr

from .config import AVISO_CONSENTIMENTO, LLM_HOST, LLM_MODELO, RESULTADOS, RAG_SCORE_MIN, RAG_TOP_K, STT_MODELO, KB_DIR
from .dialogo import Dialogo
from .llm import OllamaChat
from .pipeline import Assistente
from .rag import BaseConhecimento
from .stt import STT
from .tts import TTS


def _aquecer(stt, llm):
    """Prepara STT (GPU) e LLM (modelo na memória) antes de abrir a interface; falhas aqui não impedem o app."""
    for nome, fn in (("STT", getattr(stt, "aquecer", None)), ("LLM", getattr(llm, "aquecer", None))):
        if fn:
            try:
                fn()
                print(f"[aquecimento] {nome} pronto")
            except Exception as e:
                print(f"[aquecimento] {nome} não aqueceu: {e}")


def criar_app(stt_backend="faster-whisper", stt_modelo=STT_MODELO, llm_modelo=LLM_MODELO, aquecer=True,
              stt=None, tts=None, llm=None):
    """stt, tts e llm só são passados nos testes automáticos; no uso normal são criados aqui."""
    stt = stt or STT(stt_backend, stt_modelo)
    llm = llm or OllamaChat(llm_modelo, LLM_HOST)
    tts = tts or TTS()
    kb = BaseConhecimento(KB_DIR, RAG_TOP_K, RAG_SCORE_MIN)
    dialogo = Dialogo(llm, kb)
    saida = tempfile.mkdtemp(prefix="zelador_")
    zelador = Assistente(stt, dialogo, tts, pasta_audio_saida=saida,
                         log_csv=os.path.join(RESULTADOS, "latencia_demo.csv"))
    if aquecer:
        _aquecer(stt, llm)

    def ao_aceitar(aceito):
        return gr.update(interactive=bool(aceito)), gr.update(interactive=bool(aceito))

    def enviar(audio, chat, aceito):
        chat = list(chat or [])
        if not aceito:
            chat.append({"role": "assistant", "content": "Antes de usar, aceite o aviso de privacidade."})
            return chat, None, "", None
        if not audio:
            chat.append({"role": "assistant", "content": "Não recebi nenhum áudio. Grave ou envie um arquivo."})
            return chat, None, "", None
        try:
            r = zelador.turno_audio(audio, apagar_audio=True)      # retenção mínima: apaga o áudio após o STT
        except Exception as e:                                     # mostra o motivo na tela em vez de um "Erro" vazio
            traceback.print_exc()
            chat.append({"role": "assistant", "content": f"Desculpe, tive um problema técnico: {e}"})
            return chat, None, "", None
        chat += [{"role": "user", "content": r["transcricao"] or "(não entendi o áudio)"},
                 {"role": "assistant", "content": r["resposta"]}]
        lat = (f"**Latência (s)**: STT {r['stt_s']:.2f} | RAG {r['rag_s']:.3f} | LLM {r['llm_s']:.2f} | "
               f"adaptação {r['fala_s']:.3f} | TTS {r['tts_s']:.2f} | **total até o áudio {r['total_s']:.2f}**")
        return chat, r["audio"], lat, None

    def nova():
        zelador.nova_conversa()
        return [], None, "", None

    with gr.Blocks(title="Zelador - Assistente de voz de zeladoria urbana", delete_cache=(120, 120)) as app:
        gr.Markdown("# Zelador: relate problemas urbanos falando\nProtótipo acadêmico CitizenTech (ODS 11).")
        gr.Markdown(AVISO_CONSENTIMENTO)
        aceito = gr.Checkbox(label="Li o aviso e aceito que meu áudio seja gravado e processado", value=False)
        with gr.Row():
            with gr.Column():
                audio = gr.Audio(sources=["microphone", "upload"], type="filepath", interactive=False,
                                 label="Fale (microfone) ou envie um arquivo de áudio")
                btn = gr.Button("Enviar", variant="primary", interactive=False)
                novo = gr.Button("Nova conversa (apaga o histórico)")
            with gr.Column():
                try:
                    chat = gr.Chatbot(label="Conversa (transcrição e resposta em texto)", type="messages", height=380)
                except TypeError:                                   # versões novas do Gradio já usam "messages" por padrão
                    chat = gr.Chatbot(label="Conversa (transcrição e resposta em texto)", height=380)
                resp_audio = gr.Audio(label="Resposta falada", autoplay=True, interactive=False)
                lat = gr.Markdown()
        aceito.change(ao_aceitar, aceito, [audio, btn])
        btn.click(enviar, [audio, chat, aceito], [chat, resp_audio, lat, audio])
        novo.click(nova, None, [chat, resp_audio, lat, audio])
    return app


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--share", action="store_true", help="gera link público temporário (necessário no Colab)")
    ap.add_argument("--stt-modelo", default=STT_MODELO)
    ap.add_argument("--llm", default=LLM_MODELO)
    ap.add_argument("--sem-aquecimento", action="store_true")
    a = ap.parse_args()
    criar_app("faster-whisper", a.stt_modelo, a.llm, aquecer=not a.sem_aquecimento).launch(share=a.share)


if __name__ == "__main__":
    main()
