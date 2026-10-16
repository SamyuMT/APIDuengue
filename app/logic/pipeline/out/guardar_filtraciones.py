import json

from app.logic.pipeline.base import Contexto, Etapa


class GuardarFiltraciones(Etapa):
    """Escribe ctx.filtraciones en <carpeta_salida>/<nombre_pdf>_filtrado.json."""

    nombre = "guardar_filtraciones"

    def ejecutar(self, ctx: Contexto) -> Contexto:
        destino = ctx.carpeta_salida / f"{ctx.ruta_pdf.stem}_filtrado.json"
        destino.write_text(json.dumps(ctx.filtraciones, ensure_ascii=False, indent=4), encoding="utf-8")
        return ctx
