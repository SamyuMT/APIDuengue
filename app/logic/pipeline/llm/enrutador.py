import threading
import time
from typing import Callable

from app.logic.llm import registro
from app.logic.llm.cliente_openai import completar
from app.logic.pipeline.llm.circuit_breaker import CircuitBreaker
from app.logic.pipeline.llm.config import ConfigEvaluacion
from app.schemas.llm import Mensaje, ModeloLLM, RespuestaLLM

# Un circuit breaker por modelo, compartido entre documentos y tareas: si un proveedor
# está caído no tiene sentido que cada documento lo vuelva a descubrir.
_breakers: dict[str, CircuitBreaker] = {}
_lock = threading.Lock()

AlIntentar = Callable[..., dict]   # Recibe los campos del evento y devuelve el evento registrado


class TodosLosModelosFallaron(Exception):
    def __init__(self, mensaje: str, intentos: list[dict]):
        super().__init__(mensaje)
        self.intentos = intentos


def estado_circuitos() -> dict[str, str]:
    return {nombre: b.estado.value for nombre, b in _breakers.items()}


class EnrutadorLLM:
    """Consulta al modelo principal y, si falla, a los demás modelos vinculados (en orden).

    Resiliencia en tres capas:
    1. Reintentos con espera exponencial dentro de un mismo modelo (errores transitorios).
    2. Circuit breaker por modelo: tras varios fallos seguidos se deja de usar un tiempo.
    3. Respaldo: se pasa al siguiente modelo de la lista.

    Cada intento (ok, error u omitido por circuito abierto) se informa a `al_intentar`.
    """

    def __init__(self, modelo_principal: str | None, config: ConfigEvaluacion):
        self.modelo_principal = modelo_principal
        self.config = config

    def consultar(self, prompt: str | list[Mensaje], al_intentar: AlIntentar) -> tuple[RespuestaLLM, list[dict]]:
        """`prompt` puede ser un texto o una conversación (lista de mensajes), p. ej. para pedir una corrección."""
        mensajes = [Mensaje(rol="user", contenido=prompt)] if isinstance(prompt, str) else prompt
        intentos: list[dict] = []
        for modelo in self._modelos_en_orden():
            breaker = self._breaker(modelo.nombre)
            if not breaker.permite():
                intentos.append(al_intentar(modelo=modelo.nombre, resultado="omitido_circuito_abierto"))
                continue
            respuesta = self._con_reintentos(modelo, mensajes, breaker, intentos, al_intentar)
            if respuesta:
                return respuesta, intentos
        raise TodosLosModelosFallaron(f"Ningún modelo respondió. Circuitos: {estado_circuitos()}", intentos)

    def _con_reintentos(self, modelo, mensajes, breaker, intentos, al_intentar) -> RespuestaLLM | None:
        r = self.config.reintentos
        for n in range(1, r.intentos + 1):
            inicio = time.perf_counter()
            try:
                respuesta = completar(
                    modelo, mensajes,
                    temperatura=self.config.generacion.temperatura,
                    max_tokens=self.config.generacion.max_tokens,
                )
            except Exception as exc:
                ultimo = n == r.intentos
                if ultimo:
                    breaker.registrar_fallo()   # El circuito cuenta fallos ya agotados los reintentos
                intentos.append(al_intentar(
                    modelo=modelo.nombre, intento=n, resultado="error",
                    error=f"{type(exc).__name__}: {exc}"[:500],
                    tiempo_segundos=round(time.perf_counter() - inicio, 3),
                    circuito=breaker.estado.value,
                ))
                if not ultimo:
                    time.sleep(min(r.espera_max_s, r.espera_min_s * 2 ** (n - 1)))
                continue
            breaker.registrar_exito()
            intentos.append(al_intentar(
                modelo=modelo.nombre, intento=n, resultado="ok",
                tiempo_segundos=respuesta.tiempo_segundos, circuito=breaker.estado.value,
            ))
            return respuesta
        return None

    def _modelos_en_orden(self) -> list[ModeloLLM]:
        """Principal primero; después el resto de vinculados. Se lee el registro en cada llamada."""
        modelos = registro.listar()
        if not modelos:
            raise TodosLosModelosFallaron("No hay modelos LLM vinculados (POST /v1/llm/modelos).", [])
        return sorted(modelos, key=lambda m: m.nombre != self.modelo_principal)

    def _breaker(self, nombre: str) -> CircuitBreaker:
        cb = self.config.circuit_breaker
        with _lock:
            if nombre not in _breakers:
                _breakers[nombre] = CircuitBreaker(cb.fallos_para_abrir, cb.segundos_abierto)
            return _breakers[nombre]
