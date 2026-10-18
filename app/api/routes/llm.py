from fastapi import APIRouter, HTTPException, status

from app.schemas.llm import (
    Chat,
    ChatCreado,
    ConsultaRequest,
    CrearChatRequest,
    MensajeRequest,
    ModeloLLMRespuesta,
    RespuestaLLM,
    VincularModeloRequest,
)
from app.service.llm_service import ChatNoEncontrado, ErrorProveedorLLM, LLMService, ModeloNoVinculado

router = APIRouter(prefix="/llm", tags=["llm"])
service = LLMService()


def _http(exc: Exception) -> HTTPException:
    codigos = {ModeloNoVinculado: 404, ChatNoEncontrado: 404, ErrorProveedorLLM: 502}
    return HTTPException(status_code=codigos.get(type(exc), 400), detail=str(exc))


# --- Modelos ----------------------------------------------------------

@router.get("/modelos", response_model=list[ModeloLLMRespuesta])
async def listar_modelos() -> list[ModeloLLMRespuesta]:
    """Modelos vinculados. Nunca devuelve llaves, solo si están configuradas."""
    return await service.listar_modelos()


@router.post("/modelos", response_model=ModeloLLMRespuesta, status_code=status.HTTP_201_CREATED)
async def vincular_modelo(body: VincularModeloRequest) -> ModeloLLMRespuesta:
    """Vincula (o reemplaza) un modelo. Si se envía api_key, se guarda en el .env."""
    return await service.vincular_modelo(body)


@router.delete("/modelos/{nombre}", status_code=status.HTTP_204_NO_CONTENT)
async def desvincular_modelo(nombre: str) -> None:
    try:
        await service.desvincular_modelo(nombre)
    except ModeloNoVinculado as exc:
        raise _http(exc) from exc


# --- Consulta única -----------------------------------------------------

@router.post("/consulta", response_model=RespuestaLLM)
async def consultar(body: ConsultaRequest) -> RespuestaLLM:
    """Pregunta y respuesta, sin historial."""
    try:
        return await service.consultar(body)
    except (ModeloNoVinculado, ErrorProveedorLLM) as exc:
        raise _http(exc) from exc


# --- Chat ---------------------------------------------------------------

@router.post("/chats", response_model=ChatCreado, status_code=status.HTTP_201_CREATED)
async def crear_chat(body: CrearChatRequest) -> ChatCreado:
    try:
        return ChatCreado(chat_id=await service.crear_chat(body.modelo, body.system))
    except ModeloNoVinculado as exc:
        raise _http(exc) from exc


@router.get("/chats/{chat_id}", response_model=Chat)
async def obtener_chat(chat_id: str) -> Chat:
    try:
        return await service.obtener_chat(chat_id)
    except ChatNoEncontrado as exc:
        raise _http(exc) from exc


@router.post("/chats/{chat_id}/mensajes", response_model=RespuestaLLM)
async def enviar_mensaje(chat_id: str, body: MensajeRequest) -> RespuestaLLM:
    """Envía un mensaje al chat; el modelo recibe todo el historial."""
    try:
        return await service.enviar_mensaje(chat_id, body)
    except (ChatNoEncontrado, ModeloNoVinculado, ErrorProveedorLLM) as exc:
        raise _http(exc) from exc
