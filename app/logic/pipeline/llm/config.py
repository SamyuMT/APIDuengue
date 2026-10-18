from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class Generacion(BaseModel):
    temperatura: float = 0
    max_tokens: int | None = None


class Reintentos(BaseModel):
    intentos: int = Field(default=2, ge=1)
    espera_min_s: float = 1
    espera_max_s: float = 10


class ConfigCircuitBreaker(BaseModel):
    fallos_para_abrir: int = Field(default=3, ge=1)
    segundos_abierto: float = 60


class ConfigValidacion(BaseModel):
    opciones: list[str] = ["SI", "NO", "PARCIAL"]
    alias: dict[str, list[str]] = {}            # opción -> formas equivalentes ("PARC" -> PARCIAL)
    reintentos: int = Field(default=2, ge=0)    # Correcciones que se piden si la respuesta no es válida
    por_defecto: str = "NO"                     # Valor si tras los reintentos sigue sin ser válida
    mensaje_correccion: str                     # Admite {respuesta} y {opciones}

    @model_validator(mode="after")
    def coherente(self) -> "ConfigValidacion":
        desconocidas = (set(self.alias) | {self.por_defecto}) - set(self.opciones)
        if desconocidas:
            raise ValueError(f"alias/por_defecto con opciones que no existen: {sorted(desconocidas)}")
        return self


class ConfigEvaluacion(BaseModel):
    """Estructura de config/evaluacion_llm.yaml."""

    version: int
    archivo_prompts: str
    generacion: Generacion = Generacion()
    reintentos: Reintentos = Reintentos()
    circuit_breaker: ConfigCircuitBreaker = ConfigCircuitBreaker()
    validacion: ConfigValidacion


class ItemPrompt(BaseModel):
    filename: str
    grupo_evaluacion: str | None = None   # Categoría de ctx.filtraciones; None = se omite
    prompt: str                           # Debe contener {contenido}


def cargar_evaluacion(config_dir: Path) -> tuple[ConfigEvaluacion, list[ItemPrompt]]:
    config = ConfigEvaluacion.model_validate(_leer(config_dir / "evaluacion_llm.yaml"))
    items = [ItemPrompt.model_validate(i) for i in _leer(config_dir / config.archivo_prompts)["items"]]
    sin_marcador = [i.filename for i in items if "{contenido}" not in i.prompt]
    if sin_marcador:
        raise ValueError(f"Prompts sin el marcador {{contenido}}: {sin_marcador}")
    return config, items


def _leer(ruta: Path) -> dict:
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el archivo de configuración '{ruta}'.")
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))
