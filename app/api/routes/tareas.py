from fastapi import APIRouter, HTTPException, status

from app.schemas.tareas import CrearTareaRequest, TareaAccion, TareaCreada, TareaRespuesta
from app.service.tarea_service import TareaEnEjecucion, TareaNoEncontrada, TareaNoEnEjecucion, TareaService

router = APIRouter(prefix="/tareas", tags=["tareas"])
service = TareaService()


@router.post("", response_model=TareaCreada, status_code=status.HTTP_202_ACCEPTED)
async def crear_tarea(body: CrearTareaRequest) -> TareaCreada:
    """Crea la tarea y la lanza en segundo plano. Devuelve el id para consultar su progreso."""
    try:
        tarea_id = await service.crear(
            body.carpeta_entrada, body.carpeta_salida, body.extractor, body.segmentar, body.modelo_embeddings
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TareaCreada(tarea_id=tarea_id)


@router.get("/pendientes", response_model=list[str])
async def tareas_pendientes() -> list[str]:
    """Tareas no completadas (interrumpidas o con errores) que se pueden reanudar."""
    return await service.pendientes()


@router.get("/{tarea_id}", response_model=TareaRespuesta)
async def estado_tarea(tarea_id: str) -> TareaRespuesta:
    """Estado, progreso y etapa actual de cada documento."""
    try:
        return await service.obtener(tarea_id)
    except TareaNoEncontrada as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{tarea_id}/reanudar", response_model=TareaCreada, status_code=status.HTTP_202_ACCEPTED)
async def reanudar_tarea(tarea_id: str) -> TareaCreada:
    """Reanuda desde el último checkpoint: solo procesa los documentos no completados."""
    try:
        return TareaCreada(tarea_id=await service.reanudar(tarea_id))
    except TareaNoEncontrada as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TareaEnEjecucion as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{tarea_id}/detener", response_model=TareaAccion, status_code=status.HTTP_202_ACCEPTED)
async def detener_tarea(tarea_id: str) -> TareaAccion:
    """Detiene una tarea en ejecución al terminar la etapa en curso. Luego se puede reanudar."""
    try:
        return TareaAccion(tarea_id=tarea_id, mensaje=await service.detener(tarea_id))
    except TareaNoEncontrada as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TareaNoEnEjecucion as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/{tarea_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_tarea(tarea_id: str) -> None:
    """Elimina el checkpoint de una tarea que no se está ejecutando. Los resultados se conservan."""
    try:
        await service.eliminar(tarea_id)
    except TareaNoEncontrada as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TareaEnEjecucion as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
