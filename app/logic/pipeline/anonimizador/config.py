import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class PatronConfig(BaseModel):
    nombre: str
    regex: str
    score: float = Field(ge=0, le=1)

    @field_validator("regex")
    @classmethod
    def compila(cls, regex: str) -> str:
        try:
            re.compile(regex)
        except re.error as exc:
            raise ValueError(f"regex inválido: {exc}") from exc
        return regex


class EntidadConfig(BaseModel):
    anonimizar: bool = True
    etiqueta: str | None = None          # Texto que reemplaza a la entidad
    patrones: list[PatronConfig] = []    # Vacío = la detecta el motor NLP

    @model_validator(mode="after")
    def etiqueta_requerida(self) -> "EntidadConfig":
        if self.anonimizar and not self.etiqueta:
            raise ValueError("una entidad con anonimizar: true necesita 'etiqueta'")
        return self


class ConfigAnonimizacion(BaseModel):
    """Estructura de config/anonimizacion.yaml, validada al cargar."""

    version: int
    idioma: str = "es"
    modelo_spacy: str
    umbral: float = Field(ge=0, le=1)
    entidades: dict[str, EntidadConfig]

    @property
    def entidades_a_anonimizar(self) -> dict[str, EntidadConfig]:
        return {nombre: e for nombre, e in self.entidades.items() if e.anonimizar}


def cargar_config(ruta: Path) -> ConfigAnonimizacion:
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el archivo de configuración '{ruta}'.")
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    return ConfigAnonimizacion.model_validate(datos)
