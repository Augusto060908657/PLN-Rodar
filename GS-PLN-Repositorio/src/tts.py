"""TTS (texto para voz) em português do Brasil com Piper (voz sintética pronta; nenhuma clonagem de voz)."""
import os, subprocess, time, urllib.request, wave

from .config import PIPER_VOZ

URL_VOZ = "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx"


def baixar_voz(modelo_onnx=PIPER_VOZ):
    """Baixa a voz pt_BR-faber-medium (e o .json) se ainda não estiver na pasta."""
    os.makedirs(os.path.dirname(os.path.abspath(modelo_onnx)), exist_ok=True)
    for url, destino in ((URL_VOZ, modelo_onnx), (URL_VOZ + ".json", modelo_onnx + ".json")):
        if not os.path.exists(destino):
            print("Baixando", os.path.basename(destino), "...")
            urllib.request.urlretrieve(url, destino)


class TTS:
    def __init__(self, modelo_onnx=PIPER_VOZ):
        self.modelo = modelo_onnx
        self.voz = None
        if not (os.path.exists(modelo_onnx) and os.path.exists(modelo_onnx + ".json")):
            try:
                baixar_voz(modelo_onnx)
            except Exception as e:
                raise FileNotFoundError(
                    f"Voz do Piper não encontrada em {modelo_onnx} e o download falhou ({e}). Baixe os arquivos "
                    f"pt_BR-faber-medium.onnx e .onnx.json de huggingface.co/rhasspy/piper-voices (pt/pt_BR/faber/medium) "
                    f"e coloque na pasta modelos/piper/.") from e
        try:
            from piper import PiperVoice
            self.voz = PiperVoice.load(modelo_onnx)
        except Exception as e:                     # cai para a linha de comando `piper`
            self.erro_api = str(e)

    def sintetizar(self, texto, saida_wav):
        """Gera o .wav e retorna os segundos gastos."""
        os.makedirs(os.path.dirname(os.path.abspath(saida_wav)), exist_ok=True)
        t0 = time.perf_counter()
        if self.voz is not None:
            with wave.open(saida_wav, "wb") as wf:
                if hasattr(self.voz, "synthesize_wav"):
                    self.voz.synthesize_wav(texto, wf)
                else:
                    self.voz.synthesize(texto, wf)
        else:
            subprocess.run(["piper", "--model", self.modelo, "--output_file", saida_wav],
                           input=texto.encode("utf-8"), check=True)
        return time.perf_counter() - t0
