import ollama
from config import OLLAMA_MODEL, OLLAMA_TEMPERATURE

SUMMARY_PROMPT = """
Eres un médico experto analizando la transcripción de una consulta de reconocimiento médico.

Extrae TODA la información clínica mencionada y organízala por estas secciones exactas:
- HISTORIA PROFESIONAL
- ANTECEDENTES FAMILIARES
- ENFERMEDADES PASADAS
- TRATAMIENTOS ACTUALES
- INTERVENCIONES QUIRÚRGICAS
- ANTECEDENTES GINECOLÓGICOS (si aplica)
- HÁBITOS
- ALERGIAS
- INMUNIZACIONES
- ACTIVIDAD FÍSICA
- ANAMNÉSIS (síntomas actuales)
- EXPLORACIÓN FÍSICA (hallazgos del médico)

REGLAS:
- Solo incluye información EXPLÍCITA en la transcripción. NO inferir.
- Si para una sección no hay información, escribe: "Sin información registrada"
- Sé conciso pero preciso
- Incluye negaciones importantes ("no fuma", "niega alergias")

TRANSCRIPCIÓN:
{transcription}

RESUMEN CLÍNICO ESTRUCTURADO:
"""


async def generate_clinical_summary(transcription: str) -> str:
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{
            "role": "user",
            "content": SUMMARY_PROMPT.format(transcription=transcription)
        }],
        options={"temperature": OLLAMA_TEMPERATURE}
    )
    return response["message"]["content"]
