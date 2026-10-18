import threading
import time
from enum import Enum


class EstadoCircuito(str, Enum):
    CERRADO = "cerrado"            # Funciona normal
    ABIERTO = "abierto"            # Bloqueado: no se le envían peticiones
    SEMIABIERTO = "semiabierto"    # Pasó el tiempo de espera: se prueba con una petición


class CircuitBreaker:
    """Patrón Circuit Breaker para un modelo LLM.

    Tras `fallos_para_abrir` fallos seguidos se abre y deja de recibir peticiones durante
    `segundos_abierto`; luego pasa a semiabierto: si la siguiente petición funciona se cierra,
    si falla se vuelve a abrir.
    """

    def __init__(self, fallos_para_abrir: int, segundos_abierto: float):
        self.fallos_para_abrir = fallos_para_abrir
        self.segundos_abierto = segundos_abierto
        self.estado = EstadoCircuito.CERRADO
        self.fallos = 0
        self._abierto_desde = 0.0
        self._lock = threading.Lock()   # Lo comparten los documentos que se procesan en paralelo

    def permite(self) -> bool:
        with self._lock:
            if self.estado == EstadoCircuito.ABIERTO:
                if time.monotonic() - self._abierto_desde < self.segundos_abierto:
                    return False
                self.estado = EstadoCircuito.SEMIABIERTO
            return True

    def registrar_exito(self) -> None:
        with self._lock:
            self.estado, self.fallos = EstadoCircuito.CERRADO, 0

    def registrar_fallo(self) -> None:
        with self._lock:
            self.fallos += 1
            if self.estado == EstadoCircuito.SEMIABIERTO or self.fallos >= self.fallos_para_abrir:
                self.estado = EstadoCircuito.ABIERTO
                self._abierto_desde = time.monotonic()
