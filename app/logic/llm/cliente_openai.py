import os
import time

from app.logic.llm.cliente_base import ClienteLLM
from app.schemas.llm import Mensaje, ModeloLLM, RespuestaLLM


class ClienteOpenAICompatible(ClienteLLM):
    """Adapta la API "chat completions" de OpenAI.

    Sirve para cualquier proveedor compatible cambiando base_url: OpenAI, Gemini, Anthropic,
    LM Studio, Ollama, vLLM...
    """

    def completar(self, modelo, mensajes, temperatura=0, max_tokens=None, formato_json=False) -> RespuestaLLM:
        from openai import OpenAI

        cliente = OpenAI(
            api_key=self._api_key(modelo),
            base_url=modelo.base_url,
            timeout=modelo.timeout_s,
            max_retries=0,   # Los reintentos los maneja quien llama (pipeline: enrutador)
        )
        extra = {"response_format": {"type": "json_object"}} if formato_json else {}
        inicio = time.perf_counter()
        r = cliente.chat.completions.create(
            model=modelo.modelo,
            messages=[{"role": m.rol, "content": m.contenido} for m in mensajes],
            temperature=temperatura,
            max_tokens=max_tokens,
            **extra,
        )
        uso = r.usage   # Algunos servidores locales no lo envían
        return RespuestaLLM(
            modelo=modelo.nombre,
            respuesta=(r.choices[0].message.content or "").strip(),
            tiempo_segundos=round(time.perf_counter() - inicio, 3),
            tokens_prompt=uso.prompt_tokens if uso else None,
            tokens_completion=uso.completion_tokens if uso else None,
            tokens_totales=uso.total_tokens if uso else None,
        )

    @staticmethod
    def _api_key(modelo: ModeloLLM) -> str:
        if not modelo.api_key_env:
            return "sin-llave"   # El cliente exige un valor aunque el servidor (local) no lo use
        llave = os.getenv(modelo.api_key_env)
        if not llave:
            raise ValueError(f"La variable '{modelo.api_key_env}' del modelo '{modelo.nombre}' no tiene valor en el .env.")
        return llave


CLIENTES: dict[str, ClienteLLM] = {
    "openai_compatible": ClienteOpenAICompatible(),
}


def completar(modelo: ModeloLLM, mensajes: list[Mensaje], **parametros) -> RespuestaLLM:
    """Punto de entrada único: elige el adaptador según modelo.tipo."""
    return CLIENTES[modelo.tipo].completar(modelo, mensajes, **parametros)
