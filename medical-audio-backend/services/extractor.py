import asyncio
import json
import re
import ollama
from config import OLLAMA_MODEL, OLLAMA_TEMPERATURE


def parse_llm_response(raw_response: str) -> dict | None:
    cleaned = re.sub(r'```json|```', '', raw_response).strip()
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def follow_transition(question: dict, selected_codes: list[str]) -> str | None:
    if not selected_codes:
        return None
    transitions = question.get("transitions", {})
    for code in selected_codes:
        if code in transitions:
            target = transitions[code]
            if target:
                return target
    return None


def build_single_question_prompt(question: dict, clinical_summary: str) -> str:
    codes_str = "\n".join(
        f"  {cid}: {label}"
        for cid, label in question.get("codes", {}).items()
    )

    return f"""
Eres un asistente médico que completa formularios de reconocimiento médico.

RESUMEN CLÍNICO DE LA CONSULTA:
{clinical_summary}

PREGUNTA A RESPONDER:
ID: {question['id']}
Texto: {question['text']}
Tipo: {question['question_type']}

CÓDIGOS DISPONIBLES:
{codes_str}

INSTRUCCIONES:
1. Basándote ÚNICAMENTE en el resumen clínico, selecciona la opción correcta.
2. Para tipo "yesno": selecciona el código de "Sí" o "No". Si no se menciona, elige "No".
3. Para tipo "multiple": selecciona TODOS los códigos aplicables.
4. Para tipo "choice": selecciona UN código (la opción más específica).
5. Para tipo "yesnoremember": selecciona "Sí", "No" o "No recuerda".
6. Para tipo "free": usa el código "#TEXTO_LIBRE#" y escribe el texto en "free_text".
7. Para "#TEXTO_LIBRE#" en cualquier tipo: incluye el texto en "free_text".
8. Si la información no está explícita en el resumen, selecciona la opción más conservativa (No, Ninguno, Sin información).
9. No inventes códigos. Usa EXACTAMENTE los códigos listados arriba.

RESPONDE ÚNICAMENTE CON ESTE JSON:
{{"selected_codes": ["CODIGO1", "CODIGO2"], "free_text": null}}
"""


async def ask_single_question(question: dict, clinical_summary: str) -> dict | None:
    prompt = build_single_question_prompt(question, clinical_summary)

    def _call_ollama():
        return ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": OLLAMA_TEMPERATURE}
        )

    response = await asyncio.to_thread(_call_ollama)
    raw = response["message"]["content"]

    result = parse_llm_response(raw)
    if not result:
        return None

    valid_codes = question.get("codes", {})
    selected = result.get("selected_codes", [])
    valid = [c for c in selected if c in valid_codes]

    if result.get("free_text") and not valid:
        for cid, label in valid_codes.items():
            if label == "#TEXTO_LIBRE#":
                valid = [cid]
                break

    if not valid and not result.get("free_text"):
        return None

    return {
        "question_id": question["id"],
        "selected_codes": valid,
        "free_text": result.get("free_text"),
    }


async def walk_module(
    module_key: str,
    clinical_summary: str,
    raw_data: dict,
) -> list:
    module = raw_data[module_key]
    q_map = {q["id"]: q for q in module["questions"]}
    entry = module["entry_question_id"]

    answers = []
    current = entry
    visited = set()

    while current and current not in visited:
        visited.add(current)
        question = q_map.get(current)
        if not question:
            break

        result = await ask_single_question(question, clinical_summary)

        if result:
            answers.append(result)
            current = follow_transition(question, result["selected_codes"])
        else:
            transitions = question.get("transitions", {})
            if transitions:
                current = next(
                    (v for v in transitions.values() if v),
                    None
                )
            else:
                break

    return answers


async def extract_all_questions(
    clinical_summary: str,
    raw_data: dict,
    module: str = "both"
) -> list:
    if module == "both":
        hist_task = walk_module("history", clinical_summary, raw_data)
        exam_task = walk_module("exam", clinical_summary, raw_data)
        hist_answers, exam_answers = await asyncio.gather(
            hist_task, exam_task
        )
        return hist_answers + exam_answers
    elif module == "history":
        return await walk_module("history", clinical_summary, raw_data)
    elif module == "exam":
        return await walk_module("exam", clinical_summary, raw_data)
    else:
        return await walk_module("history", clinical_summary, raw_data)
