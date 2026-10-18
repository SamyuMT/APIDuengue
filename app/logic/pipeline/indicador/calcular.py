from app.logic.pipeline.base import Contexto, Etapa
from app.logic.pipeline.indicador.calculo import calcular_indicador
from app.logic.pipeline.indicador.config import ConfigIndicador


class CalcularIndicador(Etapa):
    """Calcula el indicador de adherencia de la HC: ctx.indicador = {items, modulos, indicadores}."""

    nombre = "calcular_indicador"

    def __init__(self, config: ConfigIndicador):
        self.config = config

    def ejecutar(self, ctx: Contexto) -> Contexto:
        ctx.indicador = calcular_indicador(ctx.evaluaciones, self.config)
        return ctx
