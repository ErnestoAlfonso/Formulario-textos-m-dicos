# Graph Report - .  (2026-05-28)

## Corpus Check
- Corpus is ~18,806 words - fits in a single context window. You may not need a graph.

## Summary
- 57 nodes · 75 edges · 5 communities
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 12 edges (avg confidence: 0.82)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Backend Pipeline Architecture|Backend Pipeline Architecture]]
- [[_COMMUNITY_Data Models and Core Services|Data Models and Core Services]]
- [[_COMMUNITY_Medical Form Sections|Medical Form Sections]]
- [[_COMMUNITY_Frontend UI Integration|Frontend UI Integration]]
- [[_COMMUNITY_LLM Prompts and Extraction Logic|LLM Prompts and Extraction Logic]]

## God Nodes (most connected - your core abstractions)
1. `Medical History Form` - 14 edges
2. `Plan completo: Audio médico a Formulario JSON` - 11 edges
3. `Two-Step LLM Extraction Strategy` - 7 edges
4. `IA frontend integration script` - 7 edges
5. `4-Step Audio-to-Form Pipeline` - 5 edges
6. `Frontend Modal with 3 states: ready, processing, preview` - 5 edges
7. `Clinical Summary` - 3 edges
8. `142-Question Medical Form JSON` - 3 edges
9. `IA modal component` - 3 edges
10. `Demo HTML with data-* attributes for form binding` - 3 edges

## Surprising Connections (you probably didn't know these)
- `API request/response flow to /process-audio` --conceptually_related_to--> `Plan completo: Audio médico a Formulario JSON`  [INFERRED]
  medical-audio-backend/frontend/ia-integration.js → PLAN_COMPLETO.md
- `services Python package` --conceptually_related_to--> `4-Step Audio-to-Form Pipeline`  [INFERRED]
  medical-audio-backend/services/__init__.py → PLAN_COMPLETO.md
- `routers Python package` --conceptually_related_to--> `FastAPI Backend Server`  [INFERRED]
  medical-audio-backend/routers/__init__.py → PLAN_COMPLETO.md
- `models Python package` --conceptually_related_to--> `Pydantic v2 Validation`  [INFERRED]
  medical-audio-backend/models/__init__.py → PLAN_COMPLETO.md
- `Clinical Summary` --conceptually_related_to--> `Medical History Form`  [INFERRED]
  medical-audio-backend/services/summarizer.py → json_IA.json

## Hyperedges (group relationships)
- **Audio Processing Pipeline** — transcription, summarizer, extractor, mapper [EXTRACTED 1.00]

## Communities (5 total, 0 thin omitted)

### Community 0 - "Backend Pipeline Architecture"
Cohesion: 0.18
Nodes (13): API request/response flow to /process-audio, FastAPI Backend Server, Performance Metadata Tracking, Ollama + llama3.1:8b LLM, Plan completo: Audio médico a Formulario JSON, 4-Step Audio-to-Form Pipeline, Pydantic v2 Validation, Code Validation and Output Mapper (+5 more)

### Community 1 - "Data Models and Core Services"
Cohesion: 0.27
Nodes (4): Clinical Summary, FastAPI, Ollama LLM, Faster Whisper

### Community 2 - "Medical Form Sections"
Cohesion: 0.17
Nodes (12): Medical History Form, Actividad Física, Alergias, Anamnesis, Antecedentes Familiares, Antecedentes Ginecológicos, Enfermedades Pasadas, Hábitos (+4 more)

### Community 3 - "Frontend UI Integration"
Cohesion: 0.24
Nodes (12): Automatic form fill via data-question-id/data-code, Demo HTML with data-* attributes for form binding, Audio file upload handler, Frontend Modal with 3 states: ready, processing, preview, 142-Question Medical Form JSON, MediaRecorder microphone capture, Result preview and confirmation UI, Question Types: yesno, multiple, choice, yesnoremember, free (+4 more)

### Community 4 - "LLM Prompts and Extraction Logic"
Cohesion: 0.29
Nodes (7): Clinical Summary Prompt (FASE 3), Code Extraction Prompt (FASE 4), Valid Code Lookup Structure, LLM JSON Parse Error Recovery, Parallel Section Processing (asyncio.gather), Local-Only Privacy Constraint, Two-Step LLM Extraction Strategy

## Knowledge Gaps
- **25 isolated node(s):** `Faster Whisper`, `FastAPI`, `Historia Profesional`, `Antecedentes Familiares`, `Enfermedades Pasadas` (+20 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Plan completo: Audio médico a Formulario JSON` connect `Backend Pipeline Architecture` to `Frontend UI Integration`, `LLM Prompts and Extraction Logic`?**
  _High betweenness centrality (0.235) - this node is a cross-community bridge._
- **Why does `Medical History Form` connect `Medical Form Sections` to `Data Models and Core Services`?**
  _High betweenness centrality (0.129) - this node is a cross-community bridge._
- **Why does `IA frontend integration script` connect `Frontend UI Integration` to `Backend Pipeline Architecture`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Medical History Form` (e.g. with `extractor.py` and `Clinical Summary`) actually correct?**
  _`Medical History Form` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Faster Whisper`, `FastAPI`, `Historia Profesional` to the rest of the system?**
  _25 weakly-connected nodes found - possible documentation gaps or missing edges._