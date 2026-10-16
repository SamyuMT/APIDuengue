from pathlib import Path


def dividir_en_lineas(texto: str) -> list[str]:
    """Sin segmentación: cada línea no vacía del texto es una unidad."""
    return [linea.strip() for linea in texto.splitlines() if linea.strip()]


def segmentar_oraciones(texto: str, nltk_dir: Path) -> list[str]:
    """Con segmentación: oraciones en español con NLTK (punkt_tab), usando los datos locales de models/."""
    import nltk
    from nltk.tokenize import sent_tokenize

    if str(nltk_dir) not in nltk.data.path:
        nltk.data.path.insert(0, str(nltk_dir))
    oraciones = (o.strip() for o in sent_tokenize(texto, language="spanish"))
    return [o for o in oraciones if len(o) > 2]
