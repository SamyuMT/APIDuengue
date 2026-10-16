import re
from app.logic.pipeline.base import Contexto, Etapa


class LimpiarTexto(Etapa):
    """Normaliza espacios y elimina líneas vacías repetidas.

    Va ANTES de anonimizar: no cambia mayúsculas, tildes ni símbolos, porque spaCy y los
    patrones los necesitan (nombres con mayúscula, fechas con "/", direcciones con "#" y "-").
    """

    nombre = "limpiar"

    def ejecutar(self, ctx: Contexto) -> Contexto:
        lineas = (re.sub(r"[ \t]+", " ", linea).strip() for linea in ctx.texto.splitlines())
        ctx.texto = re.sub(r"\n{3,}", "\n\n", "\n".join(lineas)).strip()
        return ctx
