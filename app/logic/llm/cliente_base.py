from abc import ABC, abstractmethod

from app.schemas.llm import Mensaje, ModeloLLM, RespuestaLLM


class ClienteLLM(ABC):
    """Interfaz común de los proveedores LLM (Adapter: el 'target')."""

    @abstractmethod
    def completar(
        self,
        modelo: ModeloLLM,
        mensajes: list[Mensaje],
        temperatura: float = 0,
        max_tokens: int | None = None,
        formato_json: bool = False,
    ) -> RespuestaLLM: ...
