from pathlib import Path

BASE_DIR = Path(__file__).parent
SCHEMAS_DIR = BASE_DIR / "schemas"
JSON_PATH = SCHEMAS_DIR / "json_IA.json"

# Whisper config
WHISPER_MODEL_SIZE = "medium"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"
WHISPER_LANGUAGE = "es"
WHISPER_BEAM_SIZE = 5

# Ollama config
OLLAMA_MODEL = "llama3.1"
OLLAMA_TEMPERATURE = 0.1

# Audio formats aceptados
ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".webm"}
