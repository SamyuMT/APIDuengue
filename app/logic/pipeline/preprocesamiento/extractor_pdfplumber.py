from pathlib import Path

import pdfplumber

from app.logic.pipeline.preprocesamiento.extractor_base import ExtractorPdf, ResultadoExtraccion


class PdfPlumberExtractor(ExtractorPdf):
    """Adapta la API de pdfplumber a ExtractorPdf."""

    def extraer(self, ruta_pdf: Path) -> ResultadoExtraccion:
        with pdfplumber.open(ruta_pdf) as pdf:
            return ResultadoExtraccion(
                # extract_text() devuelve None en páginas sin texto
                texto="\n".join(page.extract_text() or "" for page in pdf.pages),
                num_paginas=len(pdf.pages),
            )
