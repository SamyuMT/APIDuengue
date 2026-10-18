import asyncio

from app.logic.llm import chats, registro
from app.logic.llm.cliente_openai import completar
from app.schemas.llm import (
    Chat,
    ConsultaRequest,
    Mensaje,
    MensajeRequest,
    ModeloLLMRespuesta,
    RespuestaLLM,
    VincularModeloRequest,
)


class ModeloNoVinculado(Exception):
    pass


class ChatNoEncontrado(Exception):
    pass


class ErrorProveedorLLM(Exception):
    """El proveedor respondió con error (llave inválida, modelo inexistente, sin conexión...)."""


class LLMService:
    """Servicio independiente de LLM: modelos vinculados, consulta única y chat con historial.

    El pipeline usa el mismo núcleo (app/logic/llm) a través de app/logic/pipeline/llm.
    """

    async def listar_modelos(self) -> list[ModeloLLMRespuesta]:
        modelos = await asyncio.to_thread(registro.listar)
        return [ModeloLLMRespuesta(**m.model_dump(), api_key_configurada=registro.api_key_configurada(m)) for m in modelos]

    async def vincular_modelo(self, datos: VincularModeloRequest) -> ModeloLLMRespuesta:
        m = await asyncio.to_thread(registro.vincular, datos)
        return ModeloLLMRespuesta(**m.model_dump(), api_key_configurada=registro.api_key_configurada(m))

    async def desvincular_modelo(self, nombre: str) -> None:
        try:
            await asyncio.to_thread(registro.desvincular, nombre)
        except KeyError as exc:
            raise ModeloNoVinculado(str(exc)) from exc

    async def consultar(self, datos: ConsultaRequest) -> RespuestaLLM:
        mensajes = ([Mensaje(rol="system", contenido=datos.system)] if datos.system else []) + [
            Mensaje(rol="user", contenido=datos.prompt)
        ]
        return await self._completar(datos.modelo, mensajes, datos.temperatura, datos.max_tokens, datos.formato_json)

    async def crear_chat(self, modelo: str, system: str | None) -> str:
        self._modelo(modelo)   # Valida que esté vinculado
        chat = await asyncio.to_thread(chats.crear, modelo, system)
        return chat.chat_id

    async def obtener_chat(self, chat_id: str) -> Chat:
        chat = await asyncio.to_thread(chats.cargar, chat_id)
        if chat is None:
            raise ChatNoEncontrado(f"Chat '{chat_id}' no encontrado.")
        return chat

    async def enviar_mensaje(self, chat_id: str, datos: MensajeRequest) -> RespuestaLLM:
        """Envía el historial completo + el mensaje nuevo; guarda la pregunta y la respuesta."""
        chat = await self.obtener_chat(chat_id)
        pregunta = Mensaje(rol="user", contenido=datos.contenido)
        respuesta = await self._completar(chat.modelo, chat.mensajes + [pregunta], datos.temperatura, datos.max_tokens)
        chat.mensajes += [pregunta, Mensaje(rol="assistant", contenido=respuesta.respuesta)]
        await asyncio.to_thread(chats.guardar, chat)
        return respuesta

    # ------------------------------------------------------------------

    def _modelo(self, nombre: str):
        try:
            return registro.obtener(nombre)
        except KeyError as exc:
            raise ModeloNoVinculado(str(exc)) from exc

    async def _completar(self, nombre, mensajes, temperatura, max_tokens, formato_json=False) -> RespuestaLLM:
        modelo = self._modelo(nombre)
        try:
            return await asyncio.to_thread(
                completar, modelo, mensajes,
                temperatura=temperatura, max_tokens=max_tokens, formato_json=formato_json,
            )
        except Exception as exc:
            raise ErrorProveedorLLM(f"{type(exc).__name__}: {exc}") from exc
