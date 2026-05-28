import asyncio
import json
import re
import ollama
from config import OLLAMA_MODEL, OLLAMA_TEMPERATURE

EXTRACTION_PROMPT = """
Eres un asistente médico que completa formularios estructurados.

Tienes el resumen clínico de una consulta y las preguntas de una sección del formulario.
Tu tarea es seleccionar los códigos correctos para cada pregunta respondida en el resumen.

RESUMEN CLÍNICO (sección relevante):
{section_summary}

PREGUNTAS DE LA SECCIÓN "{section_name}":
{questions_json}

INSTRUCCIONES:
1. Responde ÚNICAMENTE con un array JSON válido
2. Solo incluye preguntas que TENGAN respuesta en el resumen
3. Para preguntas "yesno": selecciona UN código (Sí o No)
4. Para preguntas "multiple": puedes seleccionar VARIOS códigos
5. Para preguntas "choice": selecciona UN código (frecuencia)
6. Para preguntas "yesnoremember": selecciona UN código (Sí/No/No recuerda)
7. Para preguntas "free" o cuando eliges "#TEXTO_LIBRE#": incluye el texto en "free_text"
8. Si la información no está en el resumen, NO incluyas la pregunta
9. NO inventes códigos. Usa EXACTAMENTE los codes del JSON

FORMATO DE RESPUESTA (solo este JSON, sin texto adicional):
[
  {{
    "question_id": "A1-1",
    "selected_codes": ["A1-11"],
    "free_text": null
  }},
  {{
    "question_id": "A1-121",
    "selected_codes": ["A1-12119", "A1-12122"],
    "free_text": null
  }}
]
"""


def parse_llm_json(raw_response: str) -> list:
    cleaned = re.sub(r'```json|```', '', raw_response).strip()
    match = re.search(r'\[.*\]', cleaned, re.DOTALL)
    if not match:
        return []
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return []


async def extract_section(
    section_name: str,
    questions: list,
    section_summary: str
) -> list:
    prompt = EXTRACTION_PROMPT.format(
        section_name=section_name,
        section_summary=section_summary or "Sin información registrada",
        questions_json=json.dumps(questions, ensure_ascii=False, indent=2),
    )
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": OLLAMA_TEMPERATURE}
    )
    return parse_llm_json(response["message"]["content"])


def split_summary_by_section(summary: str) -> dict:
    sections = {}
    current_section = None
    current_lines = []

    for line in summary.split("\n"):
        line_stripped = line.strip()
        if line_stripped.endswith(":") and line_stripped.isupper() or \
           (line_stripped.startswith("- ") and line_stripped[2:].strip().isupper()):
            if current_section:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = line_stripped.rstrip(":").strip("- ").strip()
            current_lines = []
        elif current_section:
            current_lines.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_lines).strip()

    return sections


async def extract_all_sections(summary: str, form_data: dict, module: str = "both") -> list:
    section_summaries = split_summary_by_section(summary)

    tasks = []
    for section_name, questions in form_data["sections"].items():
        if module == "history" and "EXPLORACIÓN" in section_name.upper():
            continue
        if module == "exam" and "EXPLORACIÓN" not in section_name.upper() and \
           module != "both":
            continue
        if module == "exam" and "EXPLORACIÓN" in section_name.upper():
            pass
        task = extract_section(
            section_name=section_name,
            questions=questions,
            section_summary=section_summaries.get(section_name, ""),
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_answers = []
    for result in results:
        if isinstance(result, list):
            all_answers.extend(result)

    return all_answers
