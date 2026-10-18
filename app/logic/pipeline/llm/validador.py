"""Comprobación de la respuesta del LLM (componente "Validador de respuesta de AI").

Solo se aceptan las opciones configuradas (SI / NO / PARCIAL). Si la respuesta no es válida se le pide
al modelo que la corrija, hasta `reintentos` veces; si aun así no lo es, se asigna `por_defecto` y el
ítem queda marcado como no válido para poder distinguirlo en el análisis.
"""
import re
import unicodedata

from app.logic.pipeline.llm.config import ConfigValidacion
from app.logic.pipeline.llm.enrutador import AlIntentar, EnrutadorLLM, TodosLosModelosFallaron
from app.schemas.llm import Mensaje, RespuestaLLM

MAX_CRUDA = 200   # Caracteres de la respuesta cruda que se guardan (evita copiar texto clínico largo)


class ValidadorRespuesta:
    def __init__(self, config: ConfigValidacion):
        self.config = config
        # forma normalizada -> opción ("PARC" -> "PARCIAL")
        self._equivalencias = {_normalizar(o): o for o in config.opciones}
        for opcion, alias in config.alias.items():
            self._equivalencias.update({_normalizar(a): opcion for a in alias})

    def interpretar(self, respuesta: str) -> str | None:
        """Opción válida a la que corresponde la respuesta, o None si no corresponde a ninguna.

        La respuesta completa (normalizada) debe ser una opción o un alias: "No estoy seguro"
        NO se toma como NO; se pide corrección.
        """
        return self._equivalencias.get(" ".join(_normalizar(respuesta).split()))

    def consultar_validado(self, enrutador: EnrutadorLLM, prompt: str, al_intentar: AlIntentar) -> dict:
        """Consulta al LLM y garantiza una respuesta dentro de las opciones.

        Devuelve los campos del ítem: respuesta, respuesta_cruda, valida, reintentos_validacion,
        modelo, tiempo y tokens (sumados entre intentos) e intentos. Los errores de conexión
        (TodosLosModelosFallaron) se propagan: los maneja la etapa.
        """
        conversacion = [Mensaje(rol="user", contenido=prompt)]
        acumulado = {"tiempo_segundos": 0.0, "tokens_prompt": 0, "tokens_completion": 0, "tokens_totales": 0}
        intentos: list[dict] = []

        for n in range(self.config.reintentos + 1):
            try:
                r, trazas = enrutador.consultar(conversacion, al_intentar)
            except TodosLosModelosFallaron as exc:
                exc.intentos = intentos + exc.intentos   # Conserva la traza de los intentos anteriores
                raise
            intentos += trazas
            _sumar(acumulado, r)
            opcion = self.interpretar(r.respuesta)
            base = {"modelo": r.modelo, "respuesta_cruda": r.respuesta[:MAX_CRUDA], "reintentos_validacion": n,
                    **acumulado, "intentos": intentos}
            if opcion:
                return {"respuesta": opcion, "valida": True, **base}

            intentos.append(al_intentar(
                modelo=r.modelo, resultado="respuesta_invalida",
                respuesta_cruda=r.respuesta[:MAX_CRUDA], intento_validacion=n + 1,
            ))
            conversacion = conversacion + [
                Mensaje(rol="assistant", contenido=r.respuesta),
                Mensaje(rol="user", contenido=self._mensaje_correccion(r.respuesta)),
            ]

        return {"respuesta": self.config.por_defecto, "valida": False, "motivo": "respuesta_invalida", **base}

    def _mensaje_correccion(self, respuesta: str) -> str:
        return self.config.mensaje_correccion.format(
            respuesta=respuesta[:MAX_CRUDA], opciones=", ".join(self.config.opciones)
        )


def _normalizar(texto: str) -> str:
    """Mayúsculas, sin tildes y sin nada que no sea letra, número o espacio."""
    texto = "".join(c for c in unicodedata.normalize("NFD", texto.upper()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Z0-9 ]", " ", texto).strip()


def _sumar(acumulado: dict, r: RespuestaLLM) -> None:
    acumulado["tiempo_segundos"] = round(acumulado["tiempo_segundos"] + r.tiempo_segundos, 3)
    for campo in ("tokens_prompt", "tokens_completion", "tokens_totales"):
        acumulado[campo] += getattr(r, campo) or 0
