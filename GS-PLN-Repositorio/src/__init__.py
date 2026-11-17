"""Zelador (CitizenTech). Remendo de compatibilidade entre faster-whisper e o PyAV (pacote `av`).

O faster-whisper chama av.open(..., metadata_errors="ignore"), argumento que o av 19.x não aceita mais
(TypeError: open() got an unexpected keyword argument 'metadata_errors'). O requirements.txt já fixa av<19 e o
STT decodifica o áudio com ffmpeg, mas este remendo garante que nenhuma outra chamada quebre."""
__versao__ = "2.0"   # o notebook confere este número para não usar uma cópia antiga do projeto

try:
    import av

    _av_open_original = av.open

    def _av_open_compat(*args, **kwargs):
        try:
            return _av_open_original(*args, **kwargs)
        except TypeError as e:
            if "metadata_errors" not in str(e):
                raise
            kwargs.pop("metadata_errors", None)
            return _av_open_original(*args, **kwargs)

    av.open = _av_open_compat
except ImportError:
    pass
