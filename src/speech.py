"""Speech to text with faster-whisper, fully local. Optional: the app works without it."""

from functools import lru_cache
import io

WHISPER_MODEL = "base.en"  # ~140 MB, fast and good enough for clear English


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


@lru_cache(maxsize=1)
def _model():
    from faster_whisper import WhisperModel
    try:
        return WhisperModel(WHISPER_MODEL, device="cuda", compute_type="float16")
    except Exception:  # no CUDA libraries for ctranslate2: fall back to CPU
        return WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")


def transcribe(audio_bytes: bytes) -> str:
    segments, _ = _model().transcribe(io.BytesIO(audio_bytes), vad_filter=True)
    return " ".join(s.text.strip() for s in segments).strip()
