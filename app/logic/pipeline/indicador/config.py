from pathlib import Path

import yaml
from pydantic import BaseModel, model_validator


class Condicional(BaseModel):
    item: str
    cuando: list[str]       # Respuestas de `item` que anulan
    anular: list[str]       # Ítems que dejan de tener valor


class Nivel(BaseModel):
    nivel: str
    desde: float            # Calificación mínima para este nivel


class ConfigIndicador(BaseModel):
    """Estructura de config/indicador.yaml."""

    version: int
    codigos: dict[str, int]
    puntajes: dict[str, float]
    sin_respuesta: str
    modulos: dict[str, str]              # clave (grupo_evaluacion) -> nombre para el reporte
    macro: dict[str, list[str]]          # indicador macro -> módulos que promedia
    niveles: list[Nivel] = []
    excluir: list[str] = []
    condicionales: list[Condicional] = []

    @model_validator(mode="after")
    def coherente(self) -> "ConfigIndicador":
        respuestas = set(self.codigos)
        if set(self.puntajes) != respuestas or self.sin_respuesta not in respuestas:
            raise ValueError("codigos, puntajes y sin_respuesta deben usar las mismas respuestas")
        desconocidos = {m for mods in self.macro.values() for m in mods} - set(self.modulos)
        if desconocidos:
            raise ValueError(f"macro usa módulos que no existen: {sorted(desconocidos)}")
        self.niveles = sorted(self.niveles, key=lambda n: n.desde, reverse=True)
        return self

    def nivel(self, calificacion: float | None) -> str | None:
        if calificacion is None:
            return None
        return next((n.nivel for n in self.niveles if calificacion >= n.desde), None)


def cargar_indicador(ruta: Path) -> ConfigIndicador:
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el archivo de configuración '{ruta}'.")
    return ConfigIndicador.model_validate(yaml.safe_load(ruta.read_text(encoding="utf-8")))
