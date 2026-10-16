import hashlib
import re
import uuid
from datetime import datetime
from pathlib import Path

from app.core.rutas import MODELS_DIR
from app.logic.document_logic import find_pdfs, validate_folder
from app.logic.pipeline.filtracion.embedder import ruta_modelo
from app.schemas.tareas import DocumentoTarea, EstadoDocumento, EstadoTarea, Progreso, Tarea

CHECKPOINT_DIR = Path(__file__).resolve().parents[2] / "data" / "tareas"
_ID_VALIDO = re.compile(r"^[\w-]+$")


def doc_id_para(ruta: Path) -> str:
    """Hash del nombre del archivo: identifica el documento sin exponer su nombre en logs."""
    return hashlib.sha256(ruta.name.encode()).hexdigest()[:12]



def crear_tarea(carpeta_entrada: str, carpeta_salida: str, extractor: str, segmentar: bool, modelo_embeddings: str) -> Tarea:
    """Valida la entrada, lista los PDF y prepara la carpeta de salida de la tarea."""
    ruta_modelo(MODELS_DIR, modelo_embeddings)   # Falla antes de empezar si el modelo no está en models/
    entrada = validate_folder(carpeta_entrada)
    pdfs = find_pdfs(entrada)
    if not pdfs:
        raise ValueError("La carpeta de entrada no contiene archivos PDF.")

    tarea_id = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
    salida = Path(carpeta_salida) / tarea_id
    salida.mkdir(parents=True, exist_ok=True)

    return Tarea(
        tarea_id=tarea_id,
        carpeta_entrada=str(entrada),
        carpeta_salida=str(salida),
        documentos={doc_id_para(p): DocumentoTarea(archivo=p.name) for p in pdfs},
        extractor=extractor,
        segmentar=segmentar,
        modelo_embeddings=modelo_embeddings,
    )


# ----------------------------------------------------------------------
# Checkpoint (un JSON por tarea)
# ----------------------------------------------------------------------

def guardar(tarea: Tarea) -> None:
    """Escritura atómica: si el proceso muere a mitad, el checkpoint anterior queda intacto."""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    destino = CHECKPOINT_DIR / f"{tarea.tarea_id}.json"
    temporal = destino.with_suffix(".tmp")
    temporal.write_text(tarea.model_dump_json(indent=2), encoding="utf-8")
    temporal.replace(destino)


def cargar(tarea_id: str) -> Tarea | None:
    if not _ID_VALIDO.match(tarea_id):
        return None
    ruta = CHECKPOINT_DIR / f"{tarea_id}.json"
    if not ruta.exists():
        return None
    return Tarea.model_validate_json(ruta.read_text(encoding="utf-8"))


def eliminar(tarea_id: str) -> None:
    """Borra solo el checkpoint. Los resultados en la carpeta de salida se conservan."""
    (CHECKPOINT_DIR / f"{tarea_id}.json").unlink(missing_ok=True)


def listar_no_completadas() -> list[str]:
    if not CHECKPOINT_DIR.exists():
        return []
    ids = []
    for ruta in sorted(CHECKPOINT_DIR.glob("*.json")):
        tarea = Tarea.model_validate_json(ruta.read_text(encoding="utf-8"))
        if tarea.estado != EstadoTarea.COMPLETADA:
            ids.append(tarea.tarea_id)
    return ids


# ----------------------------------------------------------------------
# Estado y progreso
# ----------------------------------------------------------------------

def documentos_pendientes(tarea: Tarea) -> list[DocumentoTarea]:
    """Todo lo que no esté completado se (re)procesa. Esto es lo que permite reanudar."""
    return [doc for doc in tarea.documentos.values() if doc.estado != EstadoDocumento.COMPLETADO]


def calcular_progreso(tarea: Tarea) -> Progreso:
    estados = [doc.estado for doc in tarea.documentos.values()]
    total = len(estados)
    completados = estados.count(EstadoDocumento.COMPLETADO)
    errores = estados.count(EstadoDocumento.ERROR)
    procesados = completados + errores
    return Progreso(
        total=total,
        procesados=procesados,
        completados=completados,
        errores=errores,
        porcentaje=round(procesados / total * 100, 1) if total else 0.0,
    )


def finalizar(tarea: Tarea) -> None:
    progreso = calcular_progreso(tarea)
    tarea.resumen = {"total": progreso.total, "completados": progreso.completados, "errores": progreso.errores}
    tarea.estado = (
        EstadoTarea.COMPLETADA if progreso.completados == progreso.total else EstadoTarea.COMPLETADA_CON_ERRORES
    )
    tarea.finalizada = datetime.now().isoformat(timespec="seconds")
