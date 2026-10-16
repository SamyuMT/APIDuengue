import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class Contexto:
    """Datos que viajan por el pipeline. Cada etapa lee lo que necesita y agrega lo suyo."""

    doc_id: str
    ruta_pdf: Path
    carpeta_salida: Path

    # --- extraer / limpiar ---
    num_paginas: int = 0
    texto: str = ""

    # --- anonimizar ---
    entidades_anonimizadas: dict[str, int] = field(default_factory=dict)   # entidad -> cantidad

    # --- filtrar ---
    filtraciones: dict[str, str] = field(default_factory=dict)   # categoría -> texto relevante

    # --- trazabilidad ---
    tiempos: dict[str, float] = field(default_factory=dict)


class Etapa(ABC):
    """Un paso del pipeline. Recibe el contexto, lo transforma y lo devuelve."""

    nombre: str

    @abstractmethod
    def ejecutar(self, ctx: Contexto) -> Contexto: ...


class ErrorEtapa(Exception):
    """Falla de una etapa concreta; guarda su nombre para saber dónde se detuvo."""

    def __init__(self, etapa: str, causa: Exception):
        super().__init__(f"[{etapa}] {type(causa).__name__}: {causa}")
        self.etapa = etapa


class Pipeline:
    """Ejecuta las etapas en orden y mide cuánto tarda cada una."""

    def __init__(self, etapas: list[Etapa]):
        self.etapas = etapas

    @property
    def nombres(self) -> list[str]:
        return [e.nombre for e in self.etapas]

    def ejecutar(self, ctx: Contexto, al_cambiar_etapa: Callable[[str], None] | None = None) -> Contexto:
        for etapa in self.etapas:
            if al_cambiar_etapa:
                al_cambiar_etapa(etapa.nombre)
            inicio = time.perf_counter()
            try:
                ctx = etapa.ejecutar(ctx)
            except Exception as exc:
                raise ErrorEtapa(etapa.nombre, exc) from exc
            ctx.tiempos[etapa.nombre] = round(time.perf_counter() - inicio, 3)
        return ctx
