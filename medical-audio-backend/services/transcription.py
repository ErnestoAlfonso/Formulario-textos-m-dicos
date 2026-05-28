from faster_whisper import WhisperModel
from config import WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE, WHISPER_LANGUAGE, WHISPER_BEAM_SIZE

_model = None


def get_whisper_model():
    global _model
    if _model is None:
        _model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
    return _model


async def transcribe_audio(audio_path: str) -> str:
    model = get_whisper_model()
    segments, info = model.transcribe(
        audio_path,
        language=WHISPER_LANGUAGE,
        beam_size=WHISPER_BEAM_SIZE,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )
    return " ".join(seg.text.strip() for seg in segments)
