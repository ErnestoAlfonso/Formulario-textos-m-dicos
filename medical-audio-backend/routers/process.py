import os
import time
import tempfile

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from services.transcription import transcribe_audio
from services.summarizer import generate_clinical_summary
from services.extractor import extract_all_questions
from services.mapper import load_form, load_raw_form, validate_and_map
from config import ALLOWED_AUDIO_EXTENSIONS

router = APIRouter()
form_data = load_form()
raw_form = load_raw_form()

def get_total_questions(form_data: dict) -> int:
    return sum(len(qs) for qs in form_data["sections"].values())


@router.post("/process-audio")
async def process_audio(
    audio: UploadFile = File(...),
    module: str = Form(default="both"),
):
    start = time.time()

    ext = os.path.splitext(audio.filename or "audio.wav")[1].lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado: {ext}. Usa: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}"
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    try:
        t0 = time.time()
        transcription = await transcribe_audio(tmp_path)
        t1 = time.time()

        summary = await generate_clinical_summary(transcription)
        t2 = time.time()

        raw_answers = await extract_all_questions(summary, raw_form, module)
        t3 = time.time()

        validated = validate_and_map(raw_answers, form_data)

        total_questions = get_total_questions(form_data)
        answered_count = len(validated["history"]) + len(validated["exam"])

        return {
            "status": "ok",
            "transcription": transcription,
            "clinical_summary": summary,
            "history": {"answers": validated["history"]},
            "exam": {"answers": validated["exam"]},
            "datos_adicionales": validated["datos_adicionales"],
            "metadata": {
                "transcription_time_seconds": round(t1 - t0, 1),
                "extraction_time_seconds": round(t3 - t1, 1),
                "total_time_seconds": round(time.time() - start, 1),
                "questions_total": total_questions,
                "questions_answered": answered_count,
                "questions_walked": len(raw_answers),
                "module": module,
            },
        }
    finally:
        os.unlink(tmp_path)


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "ollama": "check ollama status",
        "whisper": "loaded" if True else "not loaded",
    }
