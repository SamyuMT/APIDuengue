from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ResultadoExtraccion:
    texto: str
    num_paginas: int


class ExtractorPdf(ABC):
    """Interfaz común que deben cumplir todos los extractores (Adapter: el 'target')."""

    @abstractmethod
    def extraer(self, ruta_pdf: Path) -> ResultadoExtraccion: ...
