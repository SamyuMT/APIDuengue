import json

from app.logic.pipeline.base import Contexto, Etapa


class GuardarIndicador(Etapa):
    """Escribe ctx.indicador en <carpeta_salida>/<nombre_pdf>_indicador.json."""

    nombre = "guardar_indicador"

    def ejecutar(self, ctx: Contexto) -> Contexto:
        destino = ctx.carpeta_salida / f"{ctx.ruta_pdf.stem}_indicador.json"
        destino.write_text(json.dumps(ctx.indicador, ensure_ascii=False, indent=2), encoding="utf-8")
        return ctx
