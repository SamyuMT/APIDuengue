import re

from app.logic.pipeline.indicador.config import ConfigIndicador


def id_item(filename: str) -> str:
    """'item14-v1' -> 'item14' (la versión del prompt no cambia el ítem)."""
    m = re.match(r"(item\d+)", filename)
    return m.group(1) if m else filename


def numero_item(item: str) -> int:
    return int(re.sub(r"\D", "", item) or 0)


def calcular_indicador(evaluaciones: list[dict], config: ConfigIndicador) -> dict:
    """Indicador de adherencia de una HC a partir de sus evaluaciones validadas.

    {
      "items":   {"item1": {"modulo", "respuesta", "codigo", "puntaje", "excluido"}, ...},
      "modulos": {"evaluacion_general": 3.0, ...},            # promedio de sus ítems que califican
      "indicadores": {"evaluacion_general": 3.0, "diagnostico": 4.2, "manejo": 3.5, "total": 3.57},
      "niveles": {"evaluacion_general": "MEDIO", ..., "total": "MEDIO"}   # módulos e indicadores
    }
    """
    respuestas = {id_item(e["filename"]): (e.get("respuesta") or config.sin_respuesta, e["grupo_evaluacion"])
                  for e in evaluaciones}
    anulados = _anulados(respuestas, config)

    items, puntajes_por_modulo = {}, {m: [] for m in config.modulos}
    for item in sorted(respuestas, key=numero_item):
        respuesta, modulo = respuestas[item]
        excluido = "no_califica" if item in config.excluir else anulados.get(item)
        puntaje = None if excluido else config.puntajes[respuesta]
        items[item] = {"modulo": modulo, "respuesta": respuesta, "codigo": config.codigos[respuesta],
                       "puntaje": puntaje, "excluido": excluido}
        if puntaje is not None and modulo in puntajes_por_modulo:
            puntajes_por_modulo[modulo].append(puntaje)

    modulos = {m: _promedio(p) for m, p in puntajes_por_modulo.items()}
    indicadores = {macro: _promedio([modulos[m] for m in mods if modulos[m] is not None])
                   for macro, mods in config.macro.items()}
    indicadores["total"] = _promedio([v for v in indicadores.values() if v is not None])
    niveles = {k: config.nivel(v) for k, v in {**modulos, **indicadores}.items()}
    return {"items": items, "modulos": modulos, "indicadores": indicadores, "niveles": niveles}


def _anulados(respuestas: dict, config: ConfigIndicador) -> dict[str, str]:
    """Ítems sin valor por una regla condicional (p. ej. ítem 14 = NO anula 17 y 18)."""
    anulados = {}
    for regla in config.condicionales:
        if respuestas.get(regla.item, (None,))[0] in regla.cuando:
            anulados.update({i: f"anulado_por_{regla.item}" for i in regla.anular})
    return anulados


def _promedio(valores: list[float]) -> float | None:
    return round(sum(valores) / len(valores), 2) if valores else None
