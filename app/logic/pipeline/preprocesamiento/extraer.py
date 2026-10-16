from typing import Literal

from app.logic.pipeline.base import Contexto, Etapa
from app.logic.pipeline.preprocesamiento.extractor_base import ExtractorPdf
from app.logic.pipeline.preprocesamiento.extractor_pdfplumber import PdfPlumberExtractor
from app.logic.pipeline.preprocesamiento.extractor_pymupdf import PyMuPdfExtractor

NombreExtractor = Literal["pymupdf", "pdfplumber"]

EXTRACTORES: dict[str, type[ExtractorPdf]] = {
    "pymupdf": PyMuPdfExtractor,
    "pdfplumber": PdfPlumberExtractor,
}

def crear_extractor(nombre: NombreExtractor) -> ExtractorPdf:
    try:
        return EXTRACTORES[nombre]()
    except KeyError:
        raise ValueError(f"Extractor '{nombre}' no soportado. Opciones: {list(EXTRACTORES)}") from None

class ExtraerTexto(Etapa):
    nombre = "extraer"

    def __init__(self, extractor: ExtractorPdf):
        self.extractor = extractor

    def ejecutar(self, ctx: Contexto) -> Contexto:
        resultado = self.extractor.extraer(ctx.ruta_pdf) # Extrae el texto del PDF usando el extractor proporcionado
        if not resultado.texto.strip():
            raise ValueError("El PDF no tiene texto extraíble (¿es escaneado?).")
        ctx.texto = resultado.texto
        ctx.num_paginas = resultado.num_paginas
        return ctx
