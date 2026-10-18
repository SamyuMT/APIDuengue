from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CONFIG_DIR = RAIZ / "config"    # YAML editables (anonimización, lista blanca)
MODELS_DIR = RAIZ / "models"    # Modelos locales: la herramienta no descarga nada al ejecutar
DATA_DIR = RAIZ / "data"        # Datos generados por el programa (checkpoints, modelos LLM vinculados, chats)
