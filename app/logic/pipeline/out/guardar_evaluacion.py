import json

from app.logic.pipeline.base import Contexto, Etapa


class GuardarEvaluacion(Etapa):
    """Escribe ctx.evaluaciones en <carpeta_salida>/<nombre_pdf>_evaluacion.json.

    Siempre guarda lo evaluado. Si algún ítem quedó sin respuesta porque fallaron todos los modelos,
    después de guardar marca el documento con error para que se pueda reanudar.
    """

    nombre = "guardar_evaluacion"

    def ejecutar(self, ctx: Contexto) -> Contexto:
        destino = ctx.carpeta_salida / f"{ctx.ruta_pdf.stem}_evaluacion.json"
        destino.write_text(json.dumps(ctx.evaluaciones, ensure_ascii=False, indent=2), encoding="utf-8")
        fallidos = [e["filename"] for e in ctx.evaluaciones if e.get("motivo") == "todos_fallaron"]
        if fallidos:
            raise RuntimeError(
                f"{len(fallidos)} ítems sin respuesta (fallaron todos los modelos). "
                f"Detalle en {destino.name} y llm_intentos.jsonl"
            )
        return ctx
