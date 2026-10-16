from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ResultadoAnonimizacion:
    texto: str
    conteo: dict[str, int]   # entidad -> cantidad reemplazada (nunca los valores)


class Anonimizador(ABC):
    """Interfaz común que deben cumplir todos los motores de anonimización (Adapter: el 'target')."""

    @abstractmethod
    def anonimizar(self, texto: str) -> ResultadoAnonimizacion: ...
