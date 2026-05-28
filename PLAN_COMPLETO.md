# Plan completo: Audio médico → Formulario JSON
## Proyecto de reconocimientos médicos asistido por IA

---

## Análisis del JSON (lo que encontramos)

Antes de planificar, es clave entender con qué estamos trabajando:

| Módulo | Secciones | Preguntas | Con texto libre |
|--------|-----------|-----------|-----------------|
| `history` | 11 | 106 | 61 |
| `exam` | 7 | 36 | 18 |
| **Total** | **18** | **142** | **79** |

**Tipos de pregunta presentes:**
- `yesno` → respuesta Sí/No con código
- `multiple` → múltiple selección de opciones con códigos
- `choice` → una opción de varias con código (frecuencia: siempre/a veces/nunca...)
- `yesnoremember` → Sí/No/No recuerda con código
- `free` → texto libre

**Estructura del árbol de decisión:**
Cada respuesta tiene un código (`A1-11`, `A1-12`, etc.) y ese código determina la siguiente
pregunta mediante `transitions`. El formulario NO es lineal — es un grafo.

**El problema central que esto genera:**
No se puede enviar el JSON completo al LLM en un prompt. Son 142 preguntas con cientos
de opciones de código. Requiere una **estrategia de extracción en 2 pasos**.

---

## Stack tecnológico (100% gratuito, 100% local)

| Componente | Herramienta | Motivo |
|-----------|-------------|--------|
| Transcripción | `faster-whisper` (medium) | Mejor STT gratis en español |
| LLM extractor | `Ollama + llama3.1:8b` | Fácil setup, buen razonamiento, gratis |
| Backend | `FastAPI + Python 3.11` | Rápido, tipado, async |
| Validación | `Pydantic v2` | Garantiza que el JSON de salida sea correcto |
| Frontend | HTML/JS nativo | Se integra al frontend existente sin frameworks |

---

## Arquitectura de la solución

```
FRONTEND (página existente)
    │
    │  1. Usuario graba o sube audio
    │  2. POST /process-audio  (multipart: audio + module)
    ▼
BACKEND FastAPI
    │
    ├─ [PASO 1] faster-whisper
    │       Audio (.mp3/.wav/.m4a) → transcripción texto
    │
    ├─ [PASO 2 - LLM] Resumen clínico estructurado
    │       Transcripción → resumen por secciones (sin códigos aún)
    │       Prompt: "extrae la información médica organizada por sección"
    │
    ├─ [PASO 3 - LLM x sección] Codificación
    │       Para cada sección del form:
    │         resumen_sección + preguntas_sección → respuestas con códigos
    │       Se hacen hasta 18 llamadas (una por sección) en paralelo
    │
    └─ [PASO 4] Mapper + Validator
            Valida que los códigos existan en el JSON
            Construye el output final
    │
    ▼
RESPUESTA JSON
    {
      "transcription": "...",
      "history": { "answers": [...] },
      "exam":    { "answers": [...] },
      "datos_adicionales": [...],
      "metadata": { ... }
    }
    │
    ▼
FRONTEND
    Autocompleta el formulario existente
    El médico revisa y confirma
```

### ¿Por qué 2 pasos en el LLM y no 1?

El JSON completo tiene 142 preguntas con cientos de opciones de código. Enviarlo todo
junto al LLM en un solo prompt genera:
- Respuestas incompletas (el modelo pierde el hilo)
- Alucinaciones de códigos (inventa IDs que no existen)
- Timeouts en modelos locales con poca VRAM

Con el resumen intermedio (Paso 2) + codificación por sección (Paso 3):
- Cada prompt de codificación tiene máximo 25 preguntas (sección ANAMNÉSIS)
- El LLM trabaja en un contexto pequeño y manejable
- Los errores son trazables a una sección específica
- Las secciones se pueden procesar en paralelo

---

## FASE 0: Preparación del entorno

### 0.1 Estructura de carpetas a crear

```
medical-audio-backend/
│
├── main.py                    # App FastAPI + CORS
├── config.py                  # Modelos, rutas, parámetros
├── requirements.txt
│
├── routers/
│   └── process.py             # POST /process-audio (endpoint principal)
│
├── services/
│   ├── transcription.py       # Whisper: audio → texto
│   ├── summarizer.py          # LLM Paso 2: texto → resumen clínico
│   ├── extractor.py           # LLM Paso 3: resumen + sección → códigos
│   └── mapper.py              # Valida códigos y construye output final
│
├── schemas/
│   └── json_IA.json           # EL JSON que nos dieron (copiarlo aquí)
│
└── models/
    └── response.py            # Modelos Pydantic para validar output
```

### 0.2 Instalación de dependencias

```bash
# Python
pip install fastapi uvicorn python-multipart faster-whisper ollama pydantic aiofiles

# Ollama (Linux/Mac)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1           # ~4.7 GB, modelo principal
```

**Nota sobre hardware:**
- Sin GPU → usar modelo `tiny` o `base` de Whisper (más lento pero funciona)
- Con GPU NVIDIA → usar `medium` o `large-v3` de Whisper (más preciso)
- RAM mínima 8 GB para Ollama con llama3.1:8b

---

## FASE 1: Preprocessing del JSON

**Archivo: `services/mapper.py`** (primera parte)

Antes de arrancar con el LLM, hay que preprocesar el JSON para tenerlo listo.
Se crean 3 estructuras de datos que se usan en todo el pipeline:

### 1.1 Índice de preguntas por sección

```python
# Para el Paso 3 (codificación), necesitamos poder filtrar 
# solo las preguntas de una sección específica.

section_index = {
    "HISTORIA PROFESIONAL": [...preguntas A1-x...],
    "ANTECEDENTES FAMILIARES": [...preguntas B1-x...],
    ...
}
```

### 1.2 Lookup de códigos válidos

```python
# Para validación: dado un question_id y un code_id,
# verificar que el código realmente existe.

valid_codes = {
    "A1-1": {"A1-11": "Si", "A1-12": "No"},
    "A1-121": {"A1-12111": "Alimentaria", ...},
    ...
}
```

### 1.3 Formato comprimido para el LLM

El JSON original tiene mucha información que el LLM no necesita (`transitions`, `entry_question_id`, etc.).
Se crea una versión reducida solo con `id`, `text`, `question_type`, y `codes`:

```python
# Input al LLM (por sección):
[
  {
    "id": "A1-1",
    "text": "¿Ha trabajado anteriormente?",
    "type": "yesno",
    "options": {"A1-11": "Si", "A1-12": "No"}
  },
  ...
]
```

Esto reduce el tamaño del prompt a la mitad.

---

## FASE 2: Transcripción con Whisper

**Archivo: `services/transcription.py`**

### 2.1 Inicializar el modelo

```python
from faster_whisper import WhisperModel

# Se inicializa UNA SOLA VEZ al arrancar la app (no en cada request)
model = WhisperModel("medium", device="cpu", compute_type="int8")
# Con GPU: device="cuda", compute_type="float16"
```

### 2.2 Función de transcripción

```python
async def transcribe_audio(audio_path: str) -> str:
    segments, info = model.transcribe(
        audio_path,
        language="es",          # Forzar español
        beam_size=5,
        vad_filter=True,        # Elimina silencios
        vad_parameters={
            "min_silence_duration_ms": 500
        }
    )
    return " ".join(seg.text.strip() for seg in segments)
```

**Formatos de audio aceptados:** .mp3, .wav, .m4a, .ogg, .webm (grabaciones del browser)

**Tiempo estimado:**
- Audio de 10 min en CPU (sin GPU) → ~3-5 minutos con modelo `medium`
- Audio de 10 min con GPU → ~30 segundos

---

## FASE 3: LLM - Paso 2 (resumen clínico)

**Archivo: `services/summarizer.py`**

### 3.1 Por qué este paso es necesario

La transcripción es texto conversacional caótico:
> *"Médico: ¿Y su padre, tiene algo? Paciente: Sí, mi viejo tuvo un infarto hace unos años,
> ya está bien, pero tomaba pastillas... Médico: ¿Recuerda qué pastillas? Paciente: No,
> no recuerdo."*

El LLM necesita esto como resumen estructurado antes de mapear a códigos:
> *"Antecedentes familiares - padre: tuvo infarto (pasado, actualmente bien). Medicación
> paterna: desconocida."*

### 3.2 El prompt del resumen

```python
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
```

### 3.3 Llamada a Ollama

```python
import ollama

async def generate_clinical_summary(transcription: str) -> str:
    response = ollama.chat(
        model="llama3.1",
        messages=[{
            "role": "user",
            "content": SUMMARY_PROMPT.format(transcription=transcription)
        }],
        options={"temperature": 0.1}   # Baja temperatura = respuestas más deterministas
    )
    return response["message"]["content"]
```

**Tiempo estimado:** ~15-30 segundos en CPU

---

## FASE 4: LLM - Paso 3 (codificación por sección)

**Archivo: `services/extractor.py`**

Este es el paso más crítico. Para cada sección del formulario, se hace una llamada
separada al LLM con las preguntas de esa sección y el resumen clínico.

### 4.1 El prompt de codificación

```python
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
6. Para preguntas "free" o cuando eliges "#TEXTO_LIBRE#": incluye el texto en "free_text"
7. Si la información no está en el resumen, NO incluyas la pregunta
8. NO inventes códigos. Usa EXACTAMENTE los codes del JSON

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
```

### 4.2 Procesamiento en paralelo de secciones

```python
import asyncio

async def extract_all_sections(summary: str, form_data: dict) -> dict:
    # Dividir el resumen por secciones
    section_summaries = split_summary_by_section(summary)
    
    # Crear tareas para todas las secciones en paralelo
    tasks = []
    for section_name, questions in form_data.items():
        task = extract_section(
            section_name=section_name,
            questions=questions,
            section_summary=section_summaries.get(section_name, "")
        )
        tasks.append(task)
    
    # Ejecutar todas en paralelo (reduce tiempo total)
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return combine_results(results)
```

**Nota importante:** Ollama en modo local no es realmente async. El procesamiento paralelo
mejora la organización del código pero no el tiempo total en CPU sin GPU. Con GPU, sí
hay ganancia real de tiempo.

### 4.3 Manejo de errores del LLM

El LLM a veces devuelve JSON mal formado o con texto extra. Hay que limpiarlo:

```python
import re, json

def parse_llm_json(raw_response: str) -> list:
    # Remover bloques markdown si los hay
    cleaned = re.sub(r'```json|```', '', raw_response).strip()
    
    # Encontrar el array JSON en la respuesta
    match = re.search(r'\[.*\]', cleaned, re.DOTALL)
    if not match:
        return []
    
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return []  # Sección sin datos válidos
```

---

## FASE 5: Validación y construcción del output

**Archivo: `services/mapper.py`** (segunda parte)

### 5.1 Validar que los códigos existen

```python
def validate_and_map(raw_answers: list, form_data: dict) -> list:
    validated = []
    
    for answer in raw_answers:
        q_id = answer.get("question_id")
        
        # Verificar que la pregunta existe
        question = get_question_by_id(q_id, form_data)
        if not question:
            continue
        
        # Verificar que cada código existe en esa pregunta
        valid_selected = [
            code for code in answer.get("selected_codes", [])
            if code in question["codes"]
        ]
        
        if valid_selected or answer.get("free_text"):
            validated.append({
                "question_id": q_id,
                "question_text": question["text"],
                "question_type": question["question_type"],
                "selected_codes": valid_selected,
                "selected_labels": [question["codes"][c] for c in valid_selected],
                "free_text": answer.get("free_text")
            })
    
    return validated
```

### 5.2 Formato del output final

```json
{
  "transcription": "Texto completo de la transcripción...",
  "clinical_summary": "Resumen estructurado generado por el LLM...",
  "history": {
    "answers": [
      {
        "question_id": "A1-1",
        "question_text": "¿Ha trabajado anteriormente?",
        "question_type": "yesno",
        "selected_codes": ["A1-11"],
        "selected_labels": ["Si"],
        "free_text": null
      },
      {
        "question_id": "A1-121",
        "question_text": "¿En qué tipo industria?",
        "question_type": "multiple",
        "selected_codes": ["A1-12119"],
        "selected_labels": ["Metalúrgica"],
        "free_text": null
      }
    ]
  },
  "exam": {
    "answers": [...]
  },
  "datos_adicionales": [
    "El paciente mencionó que trabaja en turno nocturno (información no mapeada en formulario)"
  ],
  "metadata": {
    "transcription_time_seconds": 45,
    "extraction_time_seconds": 90,
    "total_time_seconds": 135,
    "questions_total": 142,
    "questions_answered": 38,
    "sections_with_data": 6
  }
}
```

---

## FASE 6: Backend FastAPI (los endpoints)

**Archivo: `main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import process

app = FastAPI(title="Medical Audio Processor")

# CORS para que el frontend pueda hacer requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # En producción: poner la URL exacta del frontend
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

app.include_router(process.router)
```

**Archivo: `routers/process.py`**

```python
from fastapi import APIRouter, UploadFile, File, Form
from services.transcription import transcribe_audio
from services.summarizer import generate_clinical_summary
from services.extractor import extract_all_sections
from services.mapper import validate_and_map, load_form
import tempfile, os, time

router = APIRouter()
form_data = load_form("schemas/json_IA.json")   # Se carga una sola vez

@router.post("/process-audio")
async def process_audio(
    audio: UploadFile = File(...),
    module: str = Form(default="both")  # "history", "exam", o "both"
):
    start = time.time()
    
    # Guardar audio temporalmente
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name
    
    try:
        # Paso 1: Transcripción
        transcription = await transcribe_audio(tmp_path)
        
        # Paso 2: Resumen clínico
        summary = await generate_clinical_summary(transcription)
        
        # Paso 3: Extracción de códigos por sección
        raw_answers = await extract_all_sections(summary, form_data, module)
        
        # Paso 4: Validación y mapeo
        validated = validate_and_map(raw_answers, form_data)
        
        return {
            "status": "ok",
            "transcription": transcription,
            "clinical_summary": summary,
            "history": {"answers": validated["history"]},
            "exam": {"answers": validated["exam"]},
            "datos_adicionales": validated["datos_adicionales"],
            "metadata": {
                "total_time_seconds": round(time.time() - start, 1),
                "questions_answered": len(validated["history"]) + len(validated["exam"])
            }
        }
    finally:
        os.unlink(tmp_path)     # Limpiar archivo temporal


@router.get("/health")
async def health():
    return {"status": "ok", "ollama": check_ollama(), "whisper": "loaded"}
```

**Arrancar el servidor:**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## FASE 7: Integración en el frontend existente

### 7.1 El botón que ya existe

En la página actual hay un botón `auto_awesome Reconocimiento Asistido`.
Lo que hay que hacer es interceptarlo y conectarlo al modal de grabación.

### 7.2 Lo que hay que agregar al HTML existente

**Un modal de grabación/subida de audio:**

```html
<!-- Modal de reconocimiento asistido por IA -->
<div id="modal-ia" class="modal-ia-overlay" style="display:none">
  <div class="modal-ia-box">
    
    <!-- Estado 1: Listo para usar -->
    <div id="ia-step-ready">
      <h3>Reconocimiento Asistido por IA</h3>
      <p>Graba la consulta o sube un audio ya grabado</p>
      
      <button id="btn-grabar" onclick="iniciarGrabacion()">
        🎙 Grabar ahora
      </button>
      
      <label for="input-audio" class="btn-subir">
        📁 Subir archivo
        <input type="file" id="input-audio" accept=".mp3,.wav,.m4a,.webm" 
               onchange="subirAudio(this.files[0])" hidden>
      </label>
      
      <button onclick="cerrarModal()">Cancelar</button>
    </div>
    
    <!-- Estado 2: Procesando -->
    <div id="ia-step-processing" style="display:none">
      <div class="spinner"></div>
      <p id="ia-status-text">Transcribiendo audio...</p>
      <small>Esto puede tardar 1-3 minutos</small>
    </div>
    
    <!-- Estado 3: Previsualización del resultado -->
    <div id="ia-step-preview" style="display:none">
      <h3>Revisá el resultado antes de confirmar</h3>
      <div id="ia-preview-content"></div>
      <p id="ia-datos-adicionales"></p>
      
      <button onclick="confirmarResultado()">✓ Confirmar y rellenar</button>
      <button onclick="volverAGrabar()">↩ Volver a grabar</button>
    </div>
    
  </div>
</div>
```

### 7.3 El JavaScript que conecta todo

```javascript
let mediaRecorder, audioChunks = [], iaResultado = null;

// Interceptar el botón existente
document.addEventListener('DOMContentLoaded', () => {
  const btnIA = document.querySelector('[data-action="reconocimiento-asistido"]');
  if (btnIA) btnIA.addEventListener('click', abrirModal);
});

function abrirModal() {
  document.getElementById('modal-ia').style.display = 'flex';
  mostrarEstado('ready');
}

async function iniciarGrabacion() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
  audioChunks = [];
  
  mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
  mediaRecorder.onstop = async () => {
    const blob = new Blob(audioChunks, { type: 'audio/webm' });
    await procesarAudio(blob, 'grabacion.webm');
  };
  
  mediaRecorder.start();
  // Cambiar botón a "Detener grabación"
}

async function subirAudio(file) {
  await procesarAudio(file, file.name);
}

async function procesarAudio(audioBlob, filename) {
  mostrarEstado('processing');
  actualizarStatus('Transcribiendo audio...');
  
  const formData = new FormData();
  formData.append('audio', audioBlob, filename);
  formData.append('module', 'both');
  
  try {
    // A los 30s cambiar el mensaje (la transcripción puede tardar)
    setTimeout(() => actualizarStatus('Analizando con IA...'), 30000);
    
    const response = await fetch('http://localhost:8000/process-audio', {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) throw new Error('Error en el servidor');
    
    iaResultado = await response.json();
    mostrarPreview(iaResultado);
    mostrarEstado('preview');
    
  } catch (error) {
    alert('Error al procesar el audio: ' + error.message);
    mostrarEstado('ready');
  }
}

function mostrarPreview(resultado) {
  const container = document.getElementById('ia-preview-content');
  const answered = resultado.history.answers.concat(resultado.exam.answers);
  
  container.innerHTML = answered.map(a => `
    <div class="ia-preview-item">
      <span class="ia-question">${a.question_text}</span>
      <span class="ia-answer">${a.selected_labels.join(', ')}${a.free_text ? a.free_text : ''}</span>
    </div>
  `).join('');
  
  if (resultado.datos_adicionales.length > 0) {
    document.getElementById('ia-datos-adicionales').textContent =
      'Info adicional: ' + resultado.datos_adicionales.join(' | ');
  }
}

function confirmarResultado() {
  rellenarFormulario(iaResultado);
  cerrarModal();
}

function rellenarFormulario(resultado) {
  // Esta función depende de cómo el frontend existente maneja los campos.
  // La lógica es: para cada answer, buscar el elemento del formulario
  // correspondiente al question_id y marcar la opción correcta.
  
  const allAnswers = [
    ...resultado.history.answers,
    ...resultado.exam.answers
  ];
  
  allAnswers.forEach(answer => {
    // Buscar la fila de la pregunta en el formulario
    const row = document.querySelector(`[data-question-id="${answer.question_id}"]`);
    if (!row) return;
    
    // Marcar los códigos seleccionados
    answer.selected_codes.forEach(code => {
      const input = row.querySelector(`[data-code="${code}"]`);
      if (input) input.checked = true;
    });
    
    // Rellenar texto libre si existe
    if (answer.free_text) {
      const textInput = row.querySelector('textarea, input[type="text"]');
      if (textInput) textInput.value = answer.free_text;
    }
  });
}
```

### 7.4 Atributos data que hay que agregar al HTML existente

Para que `rellenarFormulario()` pueda encontrar los campos, hay que agregar
atributos `data-question-id` y `data-code` a los elementos del formulario.
Esto depende de cómo está construido el frontend actual y requiere revisarlo
sección por sección.

**Si el frontend es dinámico (genera preguntas desde el mismo JSON):**
Esto es automático — ya tiene los IDs. Solo hay que asegurarse de que el
JavaScript use los mismos IDs que están en `json_IA.json`.

**Si el HTML es estático:**
Hay que agregar los atributos manualmente a cada campo.

---

## FASE 8: Testing

### 8.1 Test del backend aislado

```bash
# Primero probar solo la transcripción
curl -X POST http://localhost:8000/process-audio \
  -F "audio=@test_audio.mp3" \
  -F "module=history"
```

### 8.2 Audio de prueba recomendado

Para las pruebas iniciales, grabar un audio corto (~2 minutos) con un guión
que cubra al menos estas secciones:
- Trabajo anterior: sí, industria metalúrgica
- Antecedentes familiares: padre con hipertensión
- Sin enfermedades pasadas de interés
- Alergia al ibuprofeno
- Fumador ocasional

Luego verificar que el output JSON contenga los códigos correctos.

### 8.3 Checklist de verificación

- [ ] El audio se transcribe correctamente en español
- [ ] El resumen clínico captura los datos clave
- [ ] Los códigos del output existen en `json_IA.json`
- [ ] Las preguntas sin info quedan fuera del output (no null, sino ausentes)
- [ ] Los `datos_adicionales` capturan info no mapeada
- [ ] El formulario del frontend se rellena visualmente
- [ ] El médico puede editar campos antes de confirmar
- [ ] CORS no bloquea las requests desde el frontend

---

## FASE 9: Mejoras opcionales (por orden de impacto)

| Mejora | Herramienta | Impacto | Dificultad |
|--------|-------------|---------|------------|
| Barra de progreso en tiempo real | WebSockets (FastAPI) | Alto | Media |
| Separar voces médico/paciente | `pyannote-audio` | Alto | Alta |
| Guardar transcripciones en historial | SQLite + aiosqlite | Medio | Baja |
| UI para ver transcripción completa | Acordeón HTML | Medio | Baja |
| Confianza por respuesta (0-100%) | Prompt engineering | Medio | Media |
| Modelo más grande para español | `llama3.1:70b` (requiere GPU) | Alto | Alta |
| Cache de resultados por audio hash | Redis o dict en memoria | Bajo | Baja |

---

## Resumen del orden de implementación

```
Semana 1
├── Día 1: FASE 0 + FASE 1 — Setup y preprocessing del JSON
├── Día 2: FASE 2 — Transcripción con Whisper (probar con audios reales)
├── Día 3: FASE 3 — Resumen clínico con LLM (afinar el prompt)
├── Día 4: FASE 4 — Codificación por sección (la parte más compleja)
└── Día 5: FASE 5 + FASE 6 — Validación + endpoints FastAPI

Semana 2
├── Día 1: FASE 7 — Modal HTML/JS en el frontend
├── Día 2: FASE 7 — Función rellenarFormulario() (depende del frontend)
├── Día 3: FASE 8 — Testing end-to-end
├── Día 4: Corrección de bugs y ajuste de prompts
└── Día 5: Mejoras opcionales prioritarias
```

---

## Notas importantes

**Sobre privacidad:** El audio y la transcripción nunca salen del servidor local.
Ni Whisper ni Ollama hacen requests externos. Esto es clave para datos médicos.

**Sobre los prompts:** Los prompts de las FASES 3 y 4 van a necesitar ajuste fino
con audios reales. El primer intento raramente es perfecto. Hay que iterar.

**Sobre la sección ANTECEDENTES GINECOLÓGICOS:** Tiene 12 preguntas y solo aplica
si el paciente es mujer. El extractor debe detectar esto del audio o del contexto.

**Sobre `yesnoremember`:** Este tipo de pregunta (Sí/No/No recuerda) requiere
que el prompt explícitamente mencione que "no recuerda" es una opción válida.
Si no, el LLM tenderá a ignorarla.
