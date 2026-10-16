import re
import unicodedata

from app.logic.pipeline.base import Contexto, Etapa

_ETIQUETA = re.compile(r"(<[A-Z_]+>)")              # <NOMBRE>, <ID_DOCUMENTO>... se conservan tal cual
_NO_PERMITIDOS = re.compile(r"[^a-z0-9\s.,;:!?¿¡/%+()°\-]")


def _normalizar_tramo(texto: str) -> str:
    texto = texto.lower()
    texto = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return _NO_PERMITIDOS.sub("", texto)


class NormalizarTexto(Etapa):
    """Minúsculas, sin tildes y sin símbolos raros.

    Va DESPUÉS de anonimizar. Conserva las etiquetas de anonimización y los símbolos
    con valor clínico: fechas (17/08/2026), presión (120/80), %, °, rangos (-).
    """

    nombre = "normalizar"

    def ejecutar(self, ctx: Contexto) -> Contexto:
        tramos = _ETIQUETA.split(ctx.texto)   # Posiciones impares = etiquetas
        ctx.texto = "".join(t if i % 2 else _normalizar_tramo(t) for i, t in enumerate(tramos))
        return ctx
