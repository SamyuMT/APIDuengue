from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

NOMBRE_VALIDO = r"^[\w.\-]+$"


# ----------------------------------------------------------------------
# Modelos vinculados
# ----------------------------------------------------------------------

class ModeloLLM(BaseModel):
    """Modelo vinculado, tal como se guarda en data/llm/modelos.json (sin la llave: solo el nombre de la variable)."""

    nombre: str = Field(pattern=NOMBRE_VALIDO)    # Alias propio, p. ej. "gpt4o-mini"
    tipo: Literal["openai_compatible"] = "openai_compatible"
    modelo: str                                   # Id del proveedor, p. ej. "gpt-4o-mini"
    base_url: str | None = None                   # None = OpenAI; o Gemini, Anthropic, LM Studio, Ollama...
    api_key_env: str | None = None                # Variable del .env con la llave (None = sin llave, p. ej. local)
    timeout_s: float = 60


class VincularModeloRequest(ModeloLLM):
    api_key: str | None = None   # Si se envía, se guarda en el .env bajo api_key_env (nunca en el registro)

    model_config = {
        "json_schema_extra": {
            "example": {
                "nombre": "gpt4o-mini",
                "modelo": "gpt-4o-mini",
                "base_url": None,
                "api_key_env": "OPENAI_API_KEY",
                "api_key": "sk-...",
            }
        }
    }


class ModeloLLMRespuesta(ModeloLLM):
    api_key_configurada: bool


# ----------------------------------------------------------------------
# Consulta (pregunta y respuesta)
# ----------------------------------------------------------------------

class Mensaje(BaseModel):
    rol: Literal["system", "user", "assistant"]
    contenido: str


class ConsultaRequest(BaseModel):
    modelo: str
    prompt: str
    system: str | None = None
    temperatura: float = 0
    max_tokens: int | None = None
    formato_json: bool = False    # True = pedir al modelo una respuesta JSON


class RespuestaLLM(BaseModel):
    modelo: str
    respuesta: str
    tiempo_segundos: float
    tokens_prompt: int | None = None
    tokens_completion: int | None = None
    tokens_totales: int | None = None


# ----------------------------------------------------------------------
# Chat
# ----------------------------------------------------------------------

class CrearChatRequest(BaseModel):
    modelo: str
    system: str | None = None


class MensajeRequest(BaseModel):
    contenido: str
    temperatura: float = 0
    max_tokens: int | None = None


class Chat(BaseModel):
    chat_id: str
    modelo: str
    creado: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    mensajes: list[Mensaje] = []


class ChatCreado(BaseModel):
    chat_id: str
