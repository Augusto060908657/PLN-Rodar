"""STT (voz para texto): faster-whisper (padrão, GPU no Colab) ou Whisper ONNX via sherpa-onnx (CPU).

O áudio é decodificado aqui com ffmpeg (16 kHz, mono) e entregue ao Whisper como vetor numpy. Assim o STT não
depende da versão do pacote `av` (o av 19 quebrou o faster-whisper) e funciona com mp3, mp4, m4a, wav e webm."""
import ctypes, glob, importlib.util, os, subprocess, sys, time

import numpy as np

from .config import MODELOS_DIR

SR = 16000                       # taxa de amostragem esperada pelo Whisper


def preparar_cuda():
    """Carrega no processo atual o cuBLAS e o cuDNN instalados por pip (nvidia-cublas-cu12, nvidia-cudnn-cu12).

    Mudar os.environ['LD_LIBRARY_PATH'] depois que o Python já iniciou NÃO faz o carregador do Linux achar essas
    bibliotecas. Pré-carregá-las com ctypes resolve, mesmo dentro do kernel do Colab. Sem GPU ou sem os pacotes,
    não faz nada. Retorna a lista de bibliotecas carregadas."""
    if not sys.platform.startswith("linux"):
        return []
    pastas = []
    for nome in ("nvidia.cublas.lib", "nvidia.cudnn.lib"):
        try:
            spec = importlib.util.find_spec(nome)
        except (ImportError, ValueError):
            spec = None
        if spec and spec.submodule_search_locations:
            pastas += list(spec.submodule_search_locations)
    if not pastas:
        return []
    os.environ["LD_LIBRARY_PATH"] = ":".join(pastas + [os.environ.get("LD_LIBRARY_PATH", "")]).strip(":")
    pendentes = [lib for p in pastas for lib in sorted(glob.glob(os.path.join(p, "lib*.so*")))]
    carregadas = []
    for _ in range(2):                                   # 2 passadas: algumas bibliotecas dependem de outras
        restantes = []
        for lib in pendentes:
            try:
                ctypes.CDLL(lib, mode=ctypes.RTLD_GLOBAL)
                carregadas.append(lib)
            except OSError:
                restantes.append(lib)
        pendentes = restantes
    return carregadas


def carregar_audio(caminho, sr=SR):
    """Lê qualquer áudio/vídeo e devolve um vetor float32 mono em `sr` Hz (valores entre -1 e 1)."""
    try:
        p = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(caminho), "-vn",
                            "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
                           capture_output=True, check=True)
        return np.frombuffer(p.stdout, np.int16).astype(np.float32) / 32768.0
    except FileNotFoundError:                            # ffmpeg não instalado: tenta pelo PyAV
        from faster_whisper.audio import decode_audio
        return decode_audio(str(caminho), sampling_rate=sr)
    except subprocess.CalledProcessError as e:
        raise RuntimeError("Não consegui ler o áudio: " + e.stderr.decode("utf-8", "ignore").strip()[-200:]) from e


class STT:
    def __init__(self, backend="faster-whisper", modelo="small", device="auto", sherpa_dir=None):
        self.backend, self.modelo = backend, modelo
        if backend == "faster-whisper":
            preparar_cuda()
            if device == "auto":
                device = self._tem_gpu()
            self._carregar(device)
        elif backend == "sherpa":
            import sherpa_onnx
            d = os.path.join(sherpa_dir or MODELOS_DIR, f"sherpa-onnx-whisper-{modelo}")
            self.m = sherpa_onnx.OfflineRecognizer.from_whisper(
                encoder=f"{d}/{modelo}-encoder.int8.onnx", decoder=f"{d}/{modelo}-decoder.int8.onnx",
                tokens=f"{d}/{modelo}-tokens.txt", language="pt", task="transcribe", num_threads=4)
            self.device = "cpu"
        else:
            raise ValueError("backend deve ser 'faster-whisper' ou 'sherpa'")

    @staticmethod
    def _tem_gpu():
        try:
            import ctranslate2
            return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            return "cpu"

    def _carregar(self, device):
        from faster_whisper import WhisperModel
        try:
            self.m = WhisperModel(self.modelo, device=device, compute_type="float16" if device == "cuda" else "int8")
        except Exception as e:                           # GPU/cuDNN indisponível: usa CPU
            if device == "cpu":
                raise
            print(f"[STT] GPU indisponível ({str(e)[:120]}). Usando CPU (mais lento).")
            device = "cpu"
            self.m = WhisperModel(self.modelo, device="cpu", compute_type="int8")
        self.device = device

    def aquecer(self):
        """Faz uma transcrição curta para a primeira pergunta real não pagar o custo de iniciar a GPU."""
        if self.backend != "faster-whisper":
            return
        ruido = (np.random.RandomState(0).randn(SR) * 0.01).astype(np.float32)
        list(self.m.transcribe(ruido, language="pt", beam_size=1, vad_filter=False)[0])

    def _transcrever_fw(self, audio):
        segs, _ = self.m.transcribe(audio, language="pt", beam_size=5, vad_filter=True)
        return " ".join(s.text.strip() for s in segs).strip()

    def transcrever(self, caminho):
        """Retorna (texto, segundos gastos)."""
        t0 = time.perf_counter()
        if self.backend == "faster-whisper":
            audio = carregar_audio(caminho)
            if audio.size < SR // 5:                     # menos de 0,2 s: não há fala
                texto = ""
            else:
                try:
                    texto = self._transcrever_fw(audio)
                except RuntimeError as e:
                    if self.device == "cuda" and any(k in str(e).lower() for k in ("cudnn", "cublas", "cuda")):
                        print(f"[STT] Erro de CUDA ({str(e)[:120]}). Trocando para CPU.")
                        self._carregar("cpu")
                        texto = self._transcrever_fw(audio)
                    else:
                        raise
        else:
            import tempfile, soundfile as sf
            with tempfile.TemporaryDirectory() as tmp:
                wav = os.path.join(tmp, "a.wav")
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", caminho, "-ac", "1", "-ar", "16000", wav], check=True)
                x, sr = sf.read(wav, dtype="float32")
            s = self.m.create_stream()
            s.accept_waveform(sr, x)
            self.m.decode_stream(s)
            texto = s.result.text.strip()
        return texto, time.perf_counter() - t0
