from pathlib import Path

from app.logic.pipeline.base import Contexto, Etapa
from app.logic.pipeline.filtracion.embedder import Embedder
from app.logic.pipeline.filtracion.lista_blanca import ListaBlanca, preparar_conceptos
from app.logic.pipeline.filtracion.segmentador import dividir_en_lineas, segmentar_oraciones
from app.logic.pipeline.filtracion.similitud import buscar_coincidencias, organizar, unir_por_categoria


class FiltrarTexto(Etapa):
    """Filtrado semántico: deja solo las oraciones relevantes para la GPC, agrupadas por categoría.

    ctx.filtraciones = {"evaluacion_general": "...", "diagnostico": "...", ...}
    """

    nombre = "filtrar"

    def __init__(self, lista_blanca: ListaBlanca, embedder: Embedder, segmentar: bool, nltk_dir: Path):
        self.lista_blanca = lista_blanca
        self.embedder = embedder
        self.segmentar = segmentar
        self.nltk_dir = nltk_dir
        self.conceptos = preparar_conceptos(lista_blanca)

    def ejecutar(self, ctx: Contexto) -> Contexto:
        oraciones = segmentar_oraciones(ctx.texto, self.nltk_dir) if self.segmentar else dividir_en_lineas(ctx.texto)
        coincidencias = buscar_coincidencias(
            oraciones,
            self.embedder.generar(oraciones),
            self.conceptos,
            self.embedder.generar([c.texto for c in self.conceptos]),
            self.lista_blanca.umbral,
        )
        ctx.filtraciones = unir_por_categoria(organizar(coincidencias), list(self.lista_blanca.categorias))
        return ctx
