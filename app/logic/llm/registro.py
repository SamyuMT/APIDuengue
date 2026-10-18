import json
import os
import re

from dotenv import set_key

from app.core.rutas import DATA_DIR, RAIZ
from app.schemas.llm import ModeloLLM, VincularModeloRequest

REGISTRO = DATA_DIR / "llm" / "modelos.json"
ENV = RAIZ / ".env"


def listar() -> list[ModeloLLM]:
    if not REGISTRO.exists():
        return []
    return [ModeloLLM.model_validate(m) for m in json.loads(REGISTRO.read_text(encoding="utf-8"))]


def obtener(nombre: str) -> ModeloLLM:
    for m in listar():
        if m.nombre == nombre:
            return m
    raise KeyError(f"El modelo '{nombre}' no está vinculado. Vinculados: {[m.nombre for m in listar()]}")


def vincular(datos: VincularModeloRequest) -> ModeloLLM:
    """Agrega o reemplaza un modelo. La llave (si viene) va al .env; el registro solo guarda el nombre de la variable."""
    modelo = ModeloLLM.model_validate(datos.model_dump(exclude={"api_key"}))
    if datos.api_key:
        if not modelo.api_key_env:
            modelo.api_key_env = "LLM_" + re.sub(r"\W", "_", modelo.nombre).upper() + "_API_KEY"
        ENV.touch(exist_ok=True)
        set_key(str(ENV), modelo.api_key_env, datos.api_key)
        os.environ[modelo.api_key_env] = datos.api_key
    modelos = [m for m in listar() if m.nombre != modelo.nombre] + [modelo]
    _guardar(modelos)
    return modelo


def desvincular(nombre: str) -> None:
    obtener(nombre)   # KeyError si no existe
    _guardar([m for m in listar() if m.nombre != nombre])


def api_key_configurada(modelo: ModeloLLM) -> bool:
    return modelo.api_key_env is None or bool(os.getenv(modelo.api_key_env))


def _guardar(modelos: list[ModeloLLM]) -> None:
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    temporal = REGISTRO.with_suffix(".tmp")
    temporal.write_text(json.dumps([m.model_dump() for m in modelos], ensure_ascii=False, indent=2), encoding="utf-8")
    temporal.replace(REGISTRO)
