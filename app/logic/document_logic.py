from pathlib import Path


def validate_folder(folder: str) -> Path:
    """Valida que la ruta exista y sea un directorio."""
    path = Path(folder)
    if not path.is_dir():
        raise ValueError(f"La carpeta '{folder}' no existe o no es un directorio.")
    return path


def find_pdfs(folder: Path) -> list[Path]:
    """Devuelve los PDF de la carpeta (no recursivo), ordenados por nombre."""
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")
