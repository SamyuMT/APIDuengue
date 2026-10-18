from app.logic.pipeline.base import Contexto, Etapa
from app.logic.pipeline.llm.bitacora import Bitacora
from app.logic.pipeline.llm.config import ItemPrompt
from app.logic.pipeline.llm.enrutador import EnrutadorLLM, TodosLosModelosFallaron
from app.logic.pipeline.llm.validador import ValidadorRespuesta

ARCHIVO_BITACORA = "llm_intentos.jsonl"


class EvaluarConLLM(Etapa):
    """Evalúa cada ítem de la GPC con el LLM usando el texto filtrado de su grupo.

    ctx.evaluaciones = [{filename, grupo_evaluacion, modelo, respuesta, respuesta_cruda, valida,
                         reintentos_validacion, tiempo_segundos, tokens_*, intentos}, ...]
    - La respuesta siempre es una de las opciones (SI / NO / PARCIAL): la garantiza ValidadorRespuesta.
    - Cada intento contra un modelo se registra además en <carpeta_salida>/llm_intentos.jsonl.
    - Si ningún modelo responde un ítem, se registra (motivo: todos_fallaron) y se sigue con el resto.
    """

    nombre = "evaluar_llm"

    def __init__(self, items: list[ItemPrompt], enrutador: EnrutadorLLM, validador: ValidadorRespuesta):
        self.items = items
        self.enrutador = enrutador
        self.validador = validador

    def ejecutar(self, ctx: Contexto) -> Contexto:
        ctx.evaluaciones = []
        for item in self.items:
            if not item.grupo_evaluacion:
                continue   # Ítem sin grupo (p. ej. 28 a 30): no aplica
            contenido = ctx.filtraciones.get(item.grupo_evaluacion, "")
            base = {"filename": item.filename, "grupo_evaluacion": item.grupo_evaluacion}
            if not contenido:
                # Sin texto relevante no se gasta una consulta: se registra para que la puntuación lo vea
                ctx.evaluaciones.append({**base, "modelo": None, "respuesta": None, "motivo": "sin_contenido"})
                continue
            bitacora = Bitacora(ctx.carpeta_salida / ARCHIVO_BITACORA, doc_id=ctx.doc_id, item=item.filename)
            prompt = item.prompt.replace("{contenido}", contenido)
            try:
                resultado = self.validador.consultar_validado(self.enrutador, prompt, bitacora.registrar)
                ctx.evaluaciones.append({**base, **resultado, "intentos": _resumen(resultado["intentos"])})
            except TodosLosModelosFallaron as exc:
                ctx.evaluaciones.append({
                    **base, "modelo": None, "respuesta": None, "motivo": "todos_fallaron",
                    "error": str(exc), "intentos": _resumen(exc.intentos),
                })
        return ctx


def _resumen(intentos: list[dict]) -> list[dict]:
    """Versión corta para el JSON de evaluación (la bitácora tiene el detalle con fecha y tiempos)."""
    campos = ("modelo", "intento", "resultado", "error", "respuesta_cruda")
    return [{k: i[k] for k in campos if k in i} for i in intentos]
