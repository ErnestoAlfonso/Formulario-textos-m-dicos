import json
from pathlib import Path
from config import JSON_PATH


_form_data_cache = None


def load_form(path: Path = None) -> dict:
    global _form_data_cache
    if _form_data_cache is not None:
        return _form_data_cache
    path = path or JSON_PATH
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    _form_data_cache = preprocess_form(raw)
    return _form_data_cache


def preprocess_form(raw: dict) -> dict:
    sections = {}
    valid_codes = {}
    for module_key in ("history", "exam"):
        module = raw.get(module_key, {})
        for q in module.get("questions", []):
            section = q.get("section", "SIN SECCIÓN")
            if section not in sections:
                sections[section] = []
            compressed = {
                "id": q["id"],
                "text": q["text"],
                "type": q["question_type"],
                "options": dict(q.get("codes", {})),
            }
            sections[section].append(compressed)
            valid_codes[q["id"]] = dict(q.get("codes", {}))
    return {
        "sections": sections,
        "valid_codes": valid_codes,
        "module_map": build_module_map(raw),
    }


def build_module_map(raw: dict) -> dict:
    module_map = {}
    for module_key in ("history", "exam"):
        for q in raw.get(module_key, {}).get("questions", []):
            module_map[q["id"]] = module_key
    return module_map


def get_question_by_id(q_id: str, form_data: dict) -> dict | None:
    for section_questions in form_data["sections"].values():
        for q in section_questions:
            if q["id"] == q_id:
                return q
    return None


def validate_and_map(raw_answers: list, form_data: dict) -> dict:
    validated_history = []
    validated_exam = []
    datos_adicionales = []
    valid_codes = form_data["valid_codes"]
    module_map = form_data["module_map"]

    for answer in raw_answers:
        q_id = answer.get("question_id")
        question = get_question_by_id(q_id, form_data)
        if not question:
            continue

        valid_selected = [
            code for code in answer.get("selected_codes", [])
            if code in valid_codes.get(q_id, {})
        ]

        if valid_selected or answer.get("free_text"):
            entry = {
                "question_id": q_id,
                "question_text": question["text"],
                "question_type": question["type"],
                "selected_codes": valid_selected,
                "selected_labels": [
                    valid_codes[q_id][c] for c in valid_selected if c in valid_codes.get(q_id, {})
                ],
                "free_text": answer.get("free_text"),
            }
            target_module = module_map.get(q_id, "history")
            if target_module == "exam":
                validated_exam.append(entry)
            else:
                validated_history.append(entry)

    return {
        "history": validated_history,
        "exam": validated_exam,
        "datos_adicionales": datos_adicionales,
    }
