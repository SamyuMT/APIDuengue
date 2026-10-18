import json
import threading
from datetime import datetime
from pathlib import Path

_lock = threading.Lock()   # Varios documentos escriben en paralelo en la misma bitácora


class Bitacora:
    """Registro persistente (JSON Lines) de cada intento contra un modelo LLM.

    Se escribe al momento (append), así queda la traza aunque el proceso falle después.
    Nunca se guarda el prompt ni el texto clínico: solo modelo, resultado, error y tiempos.
    """

    def __init__(self, ruta: Path, **comunes):
        self.ruta = ruta
        self.comunes = comunes   # Campos que van en todos los eventos (p. ej. doc_id)

    def registrar(self, **evento) -> dict:
        linea = {"fecha": datetime.now().isoformat(timespec="seconds"), **self.comunes, **evento}
        with _lock:
            with self.ruta.open("a", encoding="utf-8") as f:
                f.write(json.dumps(linea, ensure_ascii=False) + "\n")
        return linea
