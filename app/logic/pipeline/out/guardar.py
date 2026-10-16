from app.logic.pipeline.base import Contexto, Etapa


class GuardarTexto(Etapa):
    """Escribe el texto procesado en <carpeta_salida>/<nombre_pdf>.txt."""

    nombre = "guardar"

    def ejecutar(self, ctx: Contexto) -> Contexto:
        destino = ctx.carpeta_salida / f"{ctx.ruta_pdf.stem}.txt"
        destino.write_text(ctx.texto, encoding="utf-8")
        return ctx
