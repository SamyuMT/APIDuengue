from pathlib import Path
import pymupdf
from app.logic.pipeline.preprocesamiento.extractor_base import ExtractorPdf, ResultadoExtraccion

class PyMuPdfExtractor(ExtractorPdf):
    def extraer(self, ruta_pdf: Path) -> ResultadoExtraccion:
        # Extraer texto del PDF usando PyMuPDF
        with pymupdf.open(ruta_pdf) as doc: # abrir el PDF con PyMuPDF
            # Extraer texto de cada página y unirlo en un solo string
            return ResultadoExtraccion(
                # retornar el texto y el número de páginas
                texto="\n".join(page.get_text() for page in doc),
                num_paginas=doc.page_count,
            )
