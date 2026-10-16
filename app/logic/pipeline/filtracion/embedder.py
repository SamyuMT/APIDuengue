import re
import threading
from pathlib import Path

_NOMBRE_VALIDO = re.compile(r"^[\w.\-]+$")
_modelos: dict[str, object] = {}     # ruta -> SentenceTransformer, compartido entre tareas
_lock = threading.Lock()


def _es_modelo(ruta: Path) -> bool:
    return (ruta / "modules.json").is_file()   # Marca de un modelo sentence-transformers


def ruta_modelo(models_dir: Path, nombre: str) -> Path:
    """Ruta de un modelo descargado en models/. Lanza ValueError si el nombre no es válido o no existe."""
    if not _NOMBRE_VALIDO.match(nombre) or nombre.strip(".") == "":
        raise ValueError(f"Nombre de modelo inválido: '{nombre}'.")
    ruta = models_dir / nombre
    if not _es_modelo(ruta):
        disponibles = sorted(p.name for p in models_dir.iterdir() if _es_modelo(p)) if models_dir.is_dir() else []
        raise ValueError(f"El modelo '{nombre}' no está en {models_dir}. Disponibles: {disponibles}")
    return ruta


class Embedder:
    """Genera embeddings con un modelo sentence-transformers cargado desde models/<nombre>.

    El modelo se carga la primera vez que se usa (no al arrancar el servidor) y se reutiliza.
    """

    def __init__(self, models_dir: Path, nombre_modelo: str):
        self.models_dir = models_dir
        self.nombre_modelo = nombre_modelo

    def generar(self, textos: list[str]):
        return self._modelo().encode(textos, convert_to_tensor=True, show_progress_bar=False)

    def _modelo(self):
        ruta = str(ruta_modelo(self.models_dir, self.nombre_modelo))
        with _lock:   # Dos documentos en paralelo no deben cargarlo dos veces
            if ruta not in _modelos:
                from sentence_transformers import SentenceTransformer

                _modelos[ruta] = SentenceTransformer(ruta, local_files_only=True)
        return _modelos[ruta]
