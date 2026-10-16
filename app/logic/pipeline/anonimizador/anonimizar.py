from app.logic.pipeline.anonimizador.anonimizador_base import Anonimizador
from app.logic.pipeline.base import Contexto, Etapa


class AnonimizarTexto(Etapa):
    """Reemplaza ctx.texto por su versión anonimizada: las etapas siguientes nunca ven el original.

    No sabe qué motor usa: recibe cualquier Anonimizador.
    """

    nombre = "anonimizar"

    def __init__(self, anonimizador: Anonimizador):
        self.anonimizador = anonimizador

    def ejecutar(self, ctx: Contexto) -> Contexto:
        resultado = self.anonimizador.anonimizar(ctx.texto)
        ctx.texto = resultado.texto
        ctx.entidades_anonimizadas = resultado.conteo
        return ctx
