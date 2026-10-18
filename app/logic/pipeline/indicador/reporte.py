"""Reporte consolidado de una tarea: Excel (una fila por HC) y JSON (por HC + general)."""
import json
from pathlib import Path

from app.logic.pipeline.indicador.calculo import numero_item
from app.logic.pipeline.indicador.config import ConfigIndicador

NOMBRE = "reporte_adherencia"


def generar_reporte(indicadores_por_hc: dict[str, dict], config: ConfigIndicador, carpeta: Path) -> list[Path]:
    """`indicadores_por_hc`: {nombre_hc: indicador de calcular_indicador}. Devuelve las rutas escritas."""
    columnas = _columnas_indicador(config)
    general = {clave: _promedio([ind[grupo][clave] for ind in indicadores_por_hc.values()])
               for clave, _, grupo in columnas}
    niveles_general = {clave: config.nivel(valor) for clave, valor in general.items()}
    rutas = [carpeta / f"{NOMBRE}.json", carpeta / f"{NOMBRE}.xlsx"]
    rutas[0].write_text(json.dumps(
        {"total_hc": len(indicadores_por_hc), "general": general, "niveles_general": niveles_general,
         "por_hc": indicadores_por_hc},
        ensure_ascii=False, indent=2,
    ), encoding="utf-8")
    _excel(indicadores_por_hc, general, niveles_general, columnas, _columnas_nivel(config), rutas[1])
    return rutas


def _columnas_indicador(config: ConfigIndicador) -> list[tuple[str, str, str]]:
    """(clave, título, dónde está en el indicador): los módulos, luego los macro y el total."""
    modulos = [(m, nombre, "modulos") for m, nombre in config.modulos.items()]
    # Los macro de un solo módulo repiten la columna del módulo: solo se agregan los que agrupan varios
    macro = [(m, _titulo(m), "indicadores") for m, mods in config.macro.items() if len(mods) > 1]
    return modulos + macro + [("total", "Calificación total", "indicadores")]


def _columnas_nivel(config: ConfigIndicador) -> list[tuple[str, str]]:
    """Nivel de los indicadores macro y del total (como el formato original de evaluación)."""
    return [(m, f"Nivel {config.modulos.get(m, _titulo(m)).lower()}") for m in config.macro] + [("total", "Nivel total")]


def _excel(por_hc: dict[str, dict], general: dict, niveles_general: dict, columnas: list, niveles: list, ruta: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    items = sorted({i for ind in por_hc.values() for i in ind["items"]}, key=numero_item)
    libro = Workbook()

    hoja = libro.active
    hoja.title = "Por HC"
    hoja.append(["Historia clínica"] + [f"item {numero_item(i)}" for i in items]
                + [t for _, t, _ in columnas] + [t for _, t in niveles])
    for nombre, ind in por_hc.items():
        codigos = [ind["items"].get(i, {}).get("codigo") for i in items]
        hoja.append([nombre] + codigos + [ind[grupo][clave] for clave, _, grupo in columnas]
                    + [ind["niveles"].get(clave) for clave, _ in niveles])

    resumen = libro.create_sheet("General")
    resumen.append(["Indicador", "Promedio", "Nivel", "HC evaluadas"])
    for clave, titulo, _ in columnas:
        resumen.append([titulo, general[clave], niveles_general[clave], len(por_hc)])

    for h in (hoja, resumen):
        for celda in h[1]:
            celda.font = Font(bold=True)
        h.freeze_panes = "B2"
    libro.save(ruta)


def _titulo(clave: str) -> str:
    return clave.replace("_", " ").capitalize()


def _promedio(valores: list) -> float | None:
    valores = [v for v in valores if v is not None]
    return round(sum(valores) / len(valores), 2) if valores else None
