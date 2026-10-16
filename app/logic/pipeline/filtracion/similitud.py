from dataclasses import dataclass

from app.logic.pipeline.filtracion.lista_blanca import Concepto


@dataclass
class Coincidencia:
    oracion: str
    score: float
    categoria: str
    subcategoria: str


def buscar_coincidencias(oraciones: list[str], emb_oraciones, conceptos: list[Concepto], emb_conceptos, umbral: float) -> list[Coincidencia]:
    """Compara cada oración con cada concepto (multietiqueta) y devuelve las >= umbral, de mayor a menor score."""
    from sentence_transformers import util

    similitudes = util.cos_sim(emb_oraciones, emb_conceptos).tolist()   # [n_oraciones][n_conceptos]
    coincidencias = [
        Coincidencia(oracion, similitudes[i][j], concepto.categoria, concepto.subcategoria)
        for j, concepto in enumerate(conceptos)
        for i, oracion in enumerate(oraciones)
        if similitudes[i][j] >= umbral
    ]
    return sorted(coincidencias, key=lambda c: c.score, reverse=True)


def organizar(coincidencias: list[Coincidencia]) -> dict[str, dict[str, list[Coincidencia]]]:
    """categoria -> subcategoria -> coincidencias, sin oraciones repetidas dentro de una subcategoría."""
    organizado: dict[str, dict[str, list[Coincidencia]]] = {}
    vistas: set[tuple[str, str, str]] = set()
    for c in coincidencias:
        clave = (c.categoria, c.subcategoria, c.oracion)
        if clave not in vistas:
            vistas.add(clave)
            organizado.setdefault(c.categoria, {}).setdefault(c.subcategoria, []).append(c)
    return organizado


def unir_por_categoria(organizado: dict[str, dict[str, list[Coincidencia]]], categorias: list[str]) -> dict[str, str]:
    """Un texto por categoría (sin repetir oraciones entre subcategorías). Toda categoría aparece, aunque sea vacía."""
    resultado = {}
    for categoria in categorias:
        oraciones = [c.oracion for sub in organizado.get(categoria, {}).values() for c in sub]
        resultado[categoria] = " ".join(dict.fromkeys(oraciones))
    return resultado
