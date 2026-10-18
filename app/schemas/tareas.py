from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

MODELO_EMBEDDINGS = "all-MiniLM-L6-v2"


class EstadoDocumento(str, Enum):
    PENDIENTE = "pendiente"
    EN_PROCESO = "en_proceso"
    COMPLETADO = "completado"
    ERROR = "error"


class EstadoTarea(str, Enum):
    EN_EJECUCION = "en_ejecucion"
    COMPLETADA = "completada"
    COMPLETADA_CON_ERRORES = "completada_con_errores"
    DETENIDA = "detenida"           # Detenida a pedido del usuario; se puede reanudar
    INTERRUMPIDA = "interrumpida"   # El servidor se detuvo a mitad de la tarea
    ERROR = "error"                 # No pudo ejecutarse (p. ej. configuración inválida)


class DocumentoTarea(BaseModel):
    archivo: str
    estado: EstadoDocumento = EstadoDocumento.PENDIENTE
    etapa: str | None = None              # Etapa actual, o en la que falló si estado = error
    error: str | None = None
    tiempos: dict[str, float] = {}        # etapa -> segundos
    indicador: dict | None = None         # {items, modulos, indicadores}; se usa en el reporte consolidado


class Tarea(BaseModel):
    """Estado completo de una tarea. Es lo que se guarda como checkpoint."""

    tarea_id: str
    estado: EstadoTarea = EstadoTarea.EN_EJECUCION
    carpeta_entrada: str
    carpeta_salida: str                   # <carpeta_salida>/<tarea_id>
    creada: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    finalizada: str | None = None
    documentos: dict[str, DocumentoTarea] = {}   # doc_id -> estado
    resumen: dict[str, int] | None = None
    error: str | None = None
    extractor: str
    segmentar: bool = True                       # True: por oraciones (NLTK); False: por líneas
    modelo_embeddings: str = MODELO_EMBEDDINGS   # Carpeta dentro de models/
    modelo_llm: str | None = None                # Modelo principal (vinculado en /v1/llm/modelos)
    reportes: list[str] = []                     # Rutas del reporte consolidado (Excel y JSON)

class Progreso(BaseModel):
    total: int
    procesados: int
    completados: int
    errores: int
    porcentaje: float


class CrearTareaRequest(BaseModel):
    carpeta_entrada: str
    carpeta_salida: str
    extractor: str # extractores (pymupdf, pdfplumber)
    segmentar: bool = True                       # Filtrado por oraciones (True) o por líneas (False)
    modelo_embeddings: str = MODELO_EMBEDDINGS   # Debe estar descargado en models/
    modelo_llm: str                              # Modelo principal; si falla se usan los demás vinculados

    model_config = {
        "json_schema_extra": {
            "example": {
                "carpeta_entrada": "D:/ProyectoGradoMaestria/tests/aprocesar",
                "carpeta_salida": "D:/ProyectoGradoMaestria/tests/resultados",
                "extractor": "pdfplumber",
                "segmentar": True,
                "modelo_embeddings": MODELO_EMBEDDINGS,
                "modelo_llm": "gpt4o-mini",
            }
        }
    }


class TareaCreada(BaseModel):
    tarea_id: str


class TareaAccion(BaseModel):
    tarea_id: str
    mensaje: str


class TareaRespuesta(Tarea):
    progreso: Progreso
    etapas: list[str]                     # Etapas del pipeline, en orden


class ResumenTareaActiva(BaseModel):
    """Una tarea que se está ejecutando ahora mismo (estado en memoria, no del checkpoint)."""

    tarea_id: str
    creada: str
    extractor: str
    modelo_llm: str | None
    progreso: Progreso
    en_curso: dict[str, str]              # archivo -> etapa actual (varios documentos en paralelo)
    deteniendo: bool                      # Se pidió detener y está terminando la etapa en curso
