from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ListaBlanca(BaseModel):
    """Estructura de config/lista_blanca.yaml: categoria -> subcategoria -> términos."""

    version: int
    umbral: float = Field(ge=0, le=1)
    categorias: dict[str, dict[str, list[str]]]


@dataclass
class Concepto:
    """Una subcategoría de la lista blanca: se compara como un solo texto."""

    categoria: str
    subcategoria: str
    texto: str


def cargar_lista_blanca(ruta: Path) -> ListaBlanca:
    if not ruta.exists():
        raise FileNotFoundError(f"No existe la lista blanca '{ruta}'.")
    return ListaBlanca.model_validate(yaml.safe_load(ruta.read_text(encoding="utf-8")))


def preparar_conceptos(lista: ListaBlanca) -> list[Concepto]:
    """Aplana la jerarquía: cada subcategoría es un concepto con sus términos unidos por comas."""
    return [
        Concepto(categoria=categoria, subcategoria=subcategoria, texto=", ".join(terminos))
        for categoria, subcategorias in lista.categorias.items()
        for subcategoria, terminos in subcategorias.items()
    ]
