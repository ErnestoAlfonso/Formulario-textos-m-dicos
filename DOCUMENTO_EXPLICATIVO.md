# Proyecto: Audio Médico → Formulario JSON

## Reconocimientos médicos ocupacionales asistidos por IA (100% local)

---

## 1. ¿Qué problema resuelve?

En los reconocimientos médicos ocupacionales, el médico realiza una entrevista al paciente y debe rellenar un **formulario digital de 142 preguntas** organizado en 18 secciones clínicas. Actualmente, el médico debe:

1. Hacer la entrevista verbal
2. Buscar manualmente cada pregunta en el formulario
3. Seleccionar la respuesta correcta entre cientos de códigos posibles
4. Navegar un árbol de decisión donde cada respuesta determina la siguiente pregunta

**Esto es lento, propenso a errores y resta tiempo a la atención médica.**

El proyecto automatiza los pasos 2-4: el médico graba la consulta, y el sistema extrae automáticamente las respuestas y rellena el formulario. El médico solo revisa y confirma.

---

## 2. El formulario médico (el "qué")

El formulario JSON (`json_IA.json`) contiene:

| Módulo | Secciones | Preguntas | Con texto libre |
|--------|-----------|-----------|-----------------|
| `history` (Historia clínica) | 11 | 106 | 61 |
| `exam` (Exploración física) | 7 | 36 | 18 |
| **Total** | **18** | **142** | **79** |

**Tipos de pregunta:**
- `yesno` → Sí / No
- `choice` → Selección única (ej: frecuencia: siempre / a veces / nunca)
- `multiple` → Selección múltiple (checkboxes)
- `yesnoremember` → Sí / No / No recuerda
- `free` → Texto libre

**El formulario es un árbol de decisión (grafo dirigido):**
- Cada pregunta tiene `codes` (las respuestas posibles) y `transitions` (qué pregunta va después según la respuesta)
- Ejemplo: "¿Ha trabajado anteriormente?" → Sí → "¿En qué tipo de industria?" → No → "¿Trabajo actual?"
- No es lineal: las respuestas determinan qué preguntas se hacen y cuáles se saltan
- Los dos módulos (history, exam) son independientes entre sí y cada uno tiene un solo punto de entrada y un solo punto terminal

---

## 3. Arquitectura técnica (el "cómo")

### Pipeline completo (4 pasos)

```
FRONTEND (HTML/JS nativo)
    │
    │  1. Médico graba audio (micrófono) o sube archivo
    │  2. POST /process-audio  (audio + módulo: history/exam/both)
    ▼
BACKEND FastAPI (localhost:8000)
    │
    ├─ [PASO 1] Transcripción
    │   faster-whisper (medium) → audio a texto
    │
    ├─ [PASO 2] Resumen clínico estructurado
    │   LLM llama3.2 (Ollama) → condensa la transcripción en
    │   un informe médico por secciones clínicas
    │
    ├─ [PASO 3] Recorrido del árbol de decisión ← NUEVO
    │   Para history y/o exam (en paralelo si ambos):
    │     while pregunta_actual != terminal:
    │       1. LLM: resumen + 1 pregunta → códigos de respuesta
    │       2. Sigue la transición del código → siguiente pregunta
    │     Cada módulo se recorre secuencialmente siguiendo el grafo
    │
    └─ [PASO 4] Validación y mapeo
        Verifica que los códigos extraídos existen en el JSON
        Convierte códigos a etiquetas legibles
    │
    ▼
RESPUESTA JSON
    {
      "transcription": "...",
      "clinical_summary": "...",
      "history": { "answers": [...] },
      "exam":    { "answers": [...] },
      "metadata": { tiempos, totals, questions_walked }
    }
    │
    ▼
FRONTEND → Auto-rellena el formulario mediante atributos
            data-question-id y data-code
            El médico revisa y pulsa "Confirmar"
```

### Stack tecnológico

| Componente | Tecnología | Propósito |
|-----------|-----------|-----------|
| Backend | Python 3.11 + FastAPI | Servidor async |
| Transcripción | faster-whisper (modelo medium) | Audio → texto (GPU) |
| LLM | Ollama + llama3.2 | Extracción clínica |
| Validación | Pydantic v2 | Estructuras de datos |
| Frontend | HTML / CSS / JS nativo | Interfaz de usuario |
| Visualización | D3.js v7 | Árbol de decisión interactivo |

---

## 4. Extracción en 2 pasos + árbol de decisión

**El problema base:** Enviar las 142 preguntas con cientos de códigos en un solo prompt provoca:
- **Alucinaciones**: el LLM inventa códigos que no existen
- **Tiempos de espera**: el contexto es demasiado grande
- **Baja precisión**: mezcla información entre secciones

### Paso 2 — Resumen clínico (1 llamada al LLM)
Condensa la transcripción en un informe médico estructurado por secciones. Elimina ruido y conversación irrelevante. Sirve como contexto para todas las preguntas siguientes.

### Paso 3 — Recorrido del árbol (secuencial por módulo)
Aquí está la clave del nuevo enfoque:

```
Enfoque anterior (por secciones):
  Sección "HISTORIA PROFESIONAL":
    LLM: "Aquí tienes las 8 preguntas de esta sección + el resumen.
          Dime qué códigos aplican para cada una."
    → El LLM decide responder 8 preguntas de golpe
    → Riesgo: responde preguntas que el médico nunca haría
      (ej: responde "Metalúrgica" aunque luego dice "No ha trabajado")

Nuevo enfoque (árbol de decisión):
  Pregunta A1-1: "¿Ha trabajado anteriormente?"
    LLM: "Resumen + 1 pregunta → código A1-11 (Sí)"
    → Transición: A1-11 → A1-121
  Pregunta A1-121: "¿En qué tipo de industria?"
    LLM: "Resumen + 1 pregunta → código A1-12119 (Metalúrgica)"
    → Transición: A1-12119 → A1-122
  ... y así hasta el final del módulo
```

**Ventajas del nuevo enfoque:**
- Sigue la **lógica real del formulario**: solo se responden preguntas alcanzables
- **Máxima precisión** por pregunta: el LLM se concentra en una sola pregunta cada vez
- **Preguntas irrelevantes se saltan solas**: si el paciente no ha trabajado, la pregunta sobre el tipo de industria nunca se hace
- **Sin alucinaciones estructurales**: no puede responder una pregunta que no debería hacerse

**Desventaja:** Es secuencial dentro de cada módulo. Sin embargo, history y exam se procesan en paralelo.

---

## 5. Componentes del proyecto

### 5.1 Backend (`medical-audio-backend/`)

| Archivo | Función |
|---------|---------|
| `main.py` | Punto de entrada FastAPI, configura CORS |
| `config.py` | Configuración: modelo Whisper, Ollama, formatos |
| `routers/process.py` | Endpoint POST /process-audio + GET /health |
| `services/transcription.py` | Transcripción con faster-whisper + VAD |
| `services/summarizer.py` | Resumen clínico con llama3.2 |
| `services/extractor.py` | **Recorrido del árbol de decisión (nuevo)** |
| `services/mapper.py` | Validación de códigos y construcción de respuesta |
| `models/response.py` | Modelos Pydantic de respuesta |
| `schemas/json_IA.json` | Copia del formulario para el backend |

### 5.2 Frontend (`medical-audio-backend/frontend/`)

| Archivo | Función |
|---------|---------|
| `demo.html` | Página demo con formulario de prueba |
| `ia-modal.html` | Modal: grabar/subir/procesar/vista previa |
| `ia-modal.css` | Estilos del modal |
| `ia-integration.js` | Grabación, llamada API, auto-relleno |

### 5.3 Herramientas adicionales

| Archivo | Función |
|---------|---------|
| `decision_tree.html` | Visualización interactiva del árbol de decisión (D3.js) |
| `guion_completo.txt` | Guión de prueba: consulta médica simulada (368 líneas) |
| `PLAN_COMPLETO.md` | Plan maestro del proyecto (850 líneas) |
| `json_IA.json` | Definición completa del formulario (2998 líneas) |

---

## 6. Visualización del árbol de decisión

El archivo `decision_tree.html` es un **explorador visual** del formulario creado con D3.js.

Aunque el pipeline ahora **recorre el árbol activamente** durante la extracción, este visualizador es una herramienta complementaria útil para desarrolladores y médicos:

- **142 nodos**, cada uno es una pregunta médica
- **Color por sección clínica** (con leyenda)
- Al hacer clic en un nodo: detalles completos (texto, códigos, transiciones)
- Filtrar por módulo: Historia / Exploración / Todos
- Zoom, pan, minimapa, ajuste automático

**Utilidad:** Permite entender visualmente la estructura del formulario, identificar secciones complejas y verificar que el recorrido del pipeline es correcto.

---

## 7. Flujo de usuario (demo)

1. El médico abre la página del formulario
2. Pulsa "Reconocimiento asistido por IA" → se abre el modal
3. Opciones:
   - **Grabar**: captura audio del micrófono en tiempo real
   - **Subir**: selecciona un archivo de audio existente
4. Selecciona el módulo: Historia, Exploración, o Ambos
5. Pulsa "Procesar"
6. El sistema muestra:
   - **Pestaña Respuestas**: respuestas extraídas organizadas por sección
   - **Pestaña Transcripción**: el texto completo del audio
   - **Pestaña Resumen**: el resumen clínico estructurado
   - **Metadatos**: tiempo de procesamiento total, preguntas recorridas
7. El médico revisa las respuestas
8. Pulsa "Confirmar" → las respuestas se rellenan automáticamente en el formulario
9. El médico hace ajustes si es necesario y guarda

---

## 8. Privacidad y requisitos

- **100% local**: Todo corre en el ordenador del médico. El audio nunca sale del equipo.
- **GPU recomendada**: NVIDIA con al menos 4GB VRAM (para Whisper)
- **RAM mínima**: 16 GB
- **Sin conexión a internet**: Una vez instalado, funciona sin conexión

---

## 9. Estado actual del proyecto

| Componente | Estado |
|-----------|--------|
| Backend (FastAPI + pipeline 4 pasos) | Implementado |
| Transcripción (faster-whisper) | Implementado |
| Resumen clínico (LLM) | Implementado |
| **Recorrido del árbol de decisión (nuevo)** | **Implementado** |
| Validación y mapeo | Implementado |
| Frontend (modal, grabación, auto-relleno) | Implementado |
| Árbol de decisión interactivo (D3.js) | Implementado |
| Guión de pruebas | Implementado |
| Pruebas con máquina real (RTX 3050) | Pendiente |
| Despliegue en entorno clínico real | Pendiente |
| Speaker diarization (opcional) | Pendiente |

---

## 10. Preguntas para la discusión

1. **Flujo:** ¿El proceso de grabar → procesar → revisar → confirmar es adecuado para la práctica clínica real?

2. **Precisión:** ¿Qué nivel de acierto en la extracción de códigos sería aceptable para considerar el sistema útil? ¿70%, 80%, 90%?

3. **UX:** ¿El médico debería poder editar respuestas antes de confirmar? ¿O es mejor que revise pregunta por pregunta?

4. **Privacidad:** ¿Hay alguna preocupación regulatoria adicional (LOPD, GDPR) más allá de tenerlo todo local?

5. **Casos complejos:** ¿Cómo manejar consultas con múltiples pacientes, interrupciones, o lenguaje coloquial?

6. **Tiempo de procesamiento:** El nuevo enfoque es secuencial. ¿Importa que tarde 1-2 minutos si la precisión es mayor?

7. **Adopción:** ¿Qué barreras ves para que los médicos adopten esta herramienta en su día a día?

---

## 11. Guía rápida para probar el proyecto

```bash
# 1. Requisitos previos
#    - Python 3.11+
#    - Ollama instalado con modelo llama3.2
#    - NVIDIA GPU con drivers CUDA (opcional pero recomendado)

# 2. Instalar dependencias
pip install -r medical-audio-backend/requirements.txt

# 3. Iniciar el backend
cd medical-audio-backend
python main.py
# → Servidor en http://localhost:8000

# 4. Abrir el frontend
#    - Abrir medical-audio-backend/frontend/demo.html en el navegador
#    - O abrir decision_tree.html para ver el árbol de decisión

# 5. Usar el guión de prueba
#    - Leer guion_completo.txt como guión para una consulta simulada
#    - Grabar o subir el audio para probar el pipeline completo
```
