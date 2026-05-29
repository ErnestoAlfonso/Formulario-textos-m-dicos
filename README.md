# Audio Médico → Formulario JSON

Reconocimientos médicos ocupacionales asistidos por IA. 100% local.

El médico graba la consulta, el sistema transcribe el audio, extrae las respuestas usando un LLM local (Ollama) recorriendo el árbol de decisión del formulario, y auto-rellena el formulario médico digital.

---

## Requisitos

- **Python 3.11 o superior**
- **Ollama** instalado con modelo `llama3.2` → [ollama.ai](https://ollama.ai)
- **NVIDIA GPU** con al menos 4GB VRAM y drivers CUDA (recomendado, funciona en CPU pero más lento) *OPCIONAL* en caso de no tener cambiar en el archivo config.py "cuda" por "cpu".
- **Git**

---

## Instalación paso a paso

### 1. Clonar el repositorio

```bash
git clone <url-del-repo>
cd "Formulario textos medicos"
```

### 2. Instalar Ollama y el modelo

```bash
# Instalar Ollama desde https://ollama.ai
# Luego descargar el modelo:
ollama pull llama3.2
```

Verifica que funciona:

```bash
ollama run llama3.2 "Hola, dime qué hace este asistente"
```

### 3. Crear el entorno virtual e instalar dependencias

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

```bash
pip install -r medical-audio-backend/requirements.txt
```

### 4. Iniciar el servidor

```bash
cd medical-audio-backend
python main.py
```

El servidor arranca en `http://localhost:8000`

### 5. Verificar que funciona

```bash
curl http://localhost:8000/health
# → {"status":"ok","ollama":"check ollama status","whisper":"loaded"}
```

---

## Cómo usarlo (desarrollador)

### Opción A — Con el frontend demo

Abre en el navegador:

```
medical-audio-backend/frontend/demo.html
```

- Pulsa "Reconocimiento asistido por IA"
- Graba o sube un audio
- Selecciona el módulo (Historia / Exploración / Ambos)
- Procesa y revisa los resultados

### Opción B — Con curl

```bash
# Subir un archivo de audio existente
curl -X POST http://localhost:8000/process-audio \
  -F "audio=@consulta.mp3" \
  -F "module=both"

# Solo historia clínica
curl -X POST http://localhost:8000/process-audio \
  -F "audio=@historia.mp3" \
  -F "module=history"
```

### Opción C — Con el guión de prueba

El archivo `guion_completo.txt` contiene un diálogo médico-paciente que cubre todas las secciones del formulario. Léelo en voz alta y grábalo para probar el pipeline completo.

---

## Estructura del proyecto

```
├── medical-audio-backend/
│   ├── main.py                 ← FastAPI entry point
│   ├── config.py               ← Configuración (modelos, rutas)
│   ├── requirements.txt        ← Dependencias Python
│   ├── routers/
│   │   └── process.py          ← POST /process-audio
│   ├── services/
│   │   ├── transcription.py    ← faster-whisper (audio → texto)
│   │   ├── summarizer.py       ← LLM (texto → resumen clínico)
│   │   ├── extractor.py        ← LLM + árbol de decisión (resumen → códigos)
│   │   └── mapper.py           ← Validación y mapeo de códigos
│   ├── models/
│   │   └── response.py         ← Pydantic models
│   ├── schemas/
│   │   └── json_IA.json        ← Formulario médico (copia)
│   └── frontend/
│       ├── demo.html           ← Página demo
│       ├── ia-modal.html       ← Modal de grabación/procesado
│       ├── ia-modal.css        ← Estilos del modal
│       └── ia-integration.js   ← Lógica frontend (grabar, API, auto-relleno)
├── json_IA.json                ← Formulario médico original (142 preguntas)
├── decision_tree.html          ← Visualización interactiva del árbol (D3.js)
├── guion_completo.txt          ← Guión de prueba para consulta simulada
├── PLAN_COMPLETO.md            ← Documentación técnica del proyecto
├── DOCUMENTO_EXPLICATIVO.md    ← Documento para presentar a compañeros
└── README.md                   ← Este archivo
```

---

## Pipeline (4 pasos)

```
Audio → [1] faster-whisper → Transcripción
     → [2] llama3.2 → Resumen clínico estructurado
     → [3] llama3.2 + árbol de decisión → Códigos por pregunta
     → [4] Validador → JSON con respuestas → Auto-relleno del formulario
```

### Paso 1: Transcripción
`faster-whisper` (modelo medium) convierte el audio a texto en español.

### Paso 2: Resumen clínico
El LLM organiza la transcripción en secciones médicas (historia profesional, antecedentes, hábitos, síntomas...).

### Paso 3: Recorrido del árbol de decisión
Para cada módulo (historia clínica / exploración física), el sistema recorre el formulario pregunta por pregunta siguiendo las transiciones del árbol de decisión. Por cada pregunta:
1. Envía al LLM el resumen clínico + la pregunta con sus códigos
2. El LLM selecciona el código correcto
3. El sistema sigue la transición del código a la siguiente pregunta

History y exam se procesan en paralelo.

### Paso 4: Validación
Verifica que todos los códigos devueltos existen en el formulario original y construye la respuesta final.

---

## API

### `POST /process-audio`

Procesa un audio y devuelve las respuestas extraídas.

**Parámetros (multipart/form-data):**

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `audio` | File | — | Archivo de audio (.mp3, .wav, .m4a, .ogg, .webm) |
| `module` | string | `"both"` | `"history"`, `"exam"` o `"both"` |

**Respuesta:**

```json
{
  "status": "ok",
  "transcription": "texto completo...",
  "clinical_summary": "resumen clínico por secciones...",
  "history": {
    "answers": [
      {
        "question_id": "A1-1",
        "question_text": "¿Ha trabajado anteriormente?",
        "question_type": "yesno",
        "selected_codes": ["A1-11"],
        "selected_labels": ["Si"],
        "free_text": null
      }
    ]
  },
  "exam": { "answers": [] },
  "metadata": {
    "transcription_time_seconds": 12.3,
    "extraction_time_seconds": 45.6,
    "total_time_seconds": 58.2,
    "questions_total": 142,
    "questions_answered": 24,
    "questions_walked": 35,
    "module": "both"
  }
}
```

### `GET /health`

```json
{"status": "ok", "ollama": "check ollama status", "whisper": "loaded"}
```

---

## Configuración

Edita `medical-audio-backend/config.py`:

```python
# Modelo Whisper
WHISPER_MODEL_SIZE = "medium"    # tiny, base, small, medium, large
WHISPER_DEVICE = "cuda"          # "cuda" o "cpu"
WHISPER_LANGUAGE = "es"

# Modelo LLM
OLLAMA_MODEL = "llama3.2"        # cualquier modelo de Ollama
OLLAMA_TEMPERATURE = 0.1
```

---

## Integración con el formulario existente

El frontend auto-rellena el formulario buscando atributos `data-question-id` y `data-code` en los elementos HTML. Ejemplo:

```html
<input type="radio" data-question-id="A1-1" data-code="A1-11" />
```

Al confirmar, el sistema recorre las respuestas y activa/rellena los elementos que coinciden con los códigos extraídos.

---

## Licencia

Proyecto interno. Uso exclusivo en entorno clínico.
