import asyncio
import logging
from pathlib import Path

from app.logic import tarea_logic
from app.logic.pipeline.base import Contexto, Pipeline
from app.logic.pipeline.flujo import construir_pipeline
from app.schemas.tareas import MODELO_EMBEDDINGS, DocumentoTarea, EstadoDocumento, EstadoTarea, Tarea, TareaRespuesta

log = logging.getLogger(__name__)


class TareaNoEncontrada(Exception):
    pass


class TareaEnEjecucion(Exception):
    pass


class TareaNoEnEjecucion(Exception):
    pass


class _DetencionSolicitada(Exception):
    """Se lanza entre etapas cuando el usuario pidió detener la tarea."""


class TareaService:
    """Crea, ejecuta en segundo plano, reanuda y consulta tareas de procesamiento de PDF.

    - Cada tarea corre como asyncio.Task: la petición HTTP responde de inmediato con el id.
    - El pipeline (síncrono) corre en un hilo para no bloquear el servidor.
    - Se guarda checkpoint después de cada documento; reanudar solo procesa los no completados.
    """

    def __init__(self, max_paralelo: int = 2):
        self._semaforo = asyncio.Semaphore(max_paralelo)   # Documentos en paralelo (todas las tareas)
        self._activas: dict[str, Tarea] = {}                 # Estado vivo de las tareas en ejecución
        self._background: set[asyncio.Task] = set()          # Referencias para que el GC no las cancele
        self._por_detener: set[str] = set()                  # Tareas a las que se pidió detener
        self._etapas = construir_pipeline("pymupdf", True, MODELO_EMBEDDINGS).nombres   # Solo para los nombres

    async def crear(self, carpeta_entrada: str, carpeta_salida: str, extractor: str, segmentar: bool, modelo_embeddings: str) -> str:
        tarea = await asyncio.to_thread(
            tarea_logic.crear_tarea, carpeta_entrada, carpeta_salida, extractor, segmentar, modelo_embeddings
        )
        tarea_logic.guardar(tarea)
        self._lanzar(tarea)
        return tarea.tarea_id

    async def reanudar(self, tarea_id: str) -> str:
        if tarea_id in self._activas:
            raise TareaEnEjecucion(f"La tarea '{tarea_id}' ya se está ejecutando.")
        self._lanzar(self._cargar(tarea_id))
        return tarea_id

    async def detener(self, tarea_id: str) -> str:
        """Pide detener la tarea. Se detiene al terminar la etapa en curso de cada documento."""
        if tarea_id not in self._activas:
            self._cargar(tarea_id)   # 404 si no existe
            raise TareaNoEnEjecucion(f"La tarea '{tarea_id}' no se está ejecutando.")
        self._por_detener.add(tarea_id)
        return "Deteniendo: termina la etapa en curso y queda en estado 'detenida' (se puede reanudar)."

    async def eliminar(self, tarea_id: str) -> None:
        """Solo se elimina si no se está ejecutando (detenida, interrumpida, con errores o finalizada)."""
        if tarea_id in self._activas:
            raise TareaEnEjecucion(f"La tarea '{tarea_id}' se está ejecutando: deténgala antes de eliminarla.")
        self._cargar(tarea_id)
        await asyncio.to_thread(tarea_logic.eliminar, tarea_id)

    async def obtener(self, tarea_id: str) -> TareaRespuesta:
        tarea = self._activas.get(tarea_id) or self._cargar(tarea_id)
        datos = tarea.model_dump()
        if tarea.estado == EstadoTarea.EN_EJECUCION and tarea_id not in self._activas:
            # El checkpoint dice "en ejecución" pero nadie la está corriendo: el servidor se detuvo
            datos["estado"] = EstadoTarea.INTERRUMPIDA
        return TareaRespuesta(**datos, progreso=tarea_logic.calcular_progreso(tarea), etapas=self._etapas)

    async def pendientes(self) -> list[str]:
        """Tareas no completadas que se pueden reanudar."""
        ids = await asyncio.to_thread(tarea_logic.listar_no_completadas)
        return [i for i in ids if i not in self._activas]


    def _cargar(self, tarea_id: str) -> Tarea:
        tarea = tarea_logic.cargar(tarea_id)
        if tarea is None:
            raise TareaNoEncontrada(f"Tarea '{tarea_id}' no encontrada.")
        return tarea

    def _lanzar(self, tarea: Tarea) -> None:
        self._activas[tarea.tarea_id] = tarea
        task = asyncio.create_task(self._ejecutar(tarea))
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def _ejecutar(self, tarea: Tarea) -> None:
        try:
            tarea.estado, tarea.error, tarea.finalizada = EstadoTarea.EN_EJECUCION, None, None
            tarea_logic.guardar(tarea)
            pipeline = construir_pipeline(tarea.extractor, tarea.segmentar, tarea.modelo_embeddings)
            await asyncio.gather(*(
                self._procesar_documento(tarea, pipeline, doc)
                for doc in tarea_logic.documentos_pendientes(tarea)
            ))
            if tarea.tarea_id in self._por_detener:
                tarea.estado = EstadoTarea.DETENIDA
                log.info("tarea %s detenida por el usuario", tarea.tarea_id)
            else:
                tarea_logic.finalizar(tarea)
                log.info("tarea %s finalizada: %s", tarea.tarea_id, tarea.resumen)
        except Exception as exc:  # Error al iniciar la tarea (no de un documento)
            tarea.estado = EstadoTarea.ERROR
            tarea.error = f"{type(exc).__name__}: {exc}"
            log.exception("tarea %s falló", tarea.tarea_id)
        finally:
            tarea_logic.guardar(tarea)
            self._activas.pop(tarea.tarea_id, None)
            self._por_detener.discard(tarea.tarea_id)

    async def _procesar_documento(self, tarea: Tarea, pipeline: Pipeline, doc: DocumentoTarea) -> None:
        async with self._semaforo:
            if tarea.tarea_id in self._por_detener:
                return   # No arranca: el documento queda pendiente
            doc.estado, doc.etapa, doc.error = EstadoDocumento.EN_PROCESO, None, None
            ctx = Contexto(
                doc_id=tarea_logic.doc_id_para(Path(doc.archivo)),
                ruta_pdf=Path(tarea.carpeta_entrada) / doc.archivo,
                carpeta_salida=Path(tarea.carpeta_salida),
            )

            def marcar_etapa(etapa: str) -> None:
                if tarea.tarea_id in self._por_detener:
                    raise _DetencionSolicitada()
                doc.etapa = etapa
            try:
                ctx = await asyncio.to_thread(pipeline.ejecutar, ctx, marcar_etapa)
                doc.estado, doc.etapa, doc.tiempos = EstadoDocumento.COMPLETADO, None, ctx.tiempos
            except _DetencionSolicitada:
                doc.estado, doc.etapa = EstadoDocumento.PENDIENTE, None   # Se reprocesa completo al reanudar
            except Exception as exc:  # Un documento con error no detiene la tarea
                doc.estado, doc.error = EstadoDocumento.ERROR, str(exc)   # doc.etapa queda en la que falló
            finally:
                tarea_logic.guardar(tarea)   # Checkpoint después de cada documento
