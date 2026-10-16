from app.core.rutas import CONFIG_DIR, MODELS_DIR
from app.logic.pipeline.anonimizador.anonimizador_presidio import PresidioAnonimizador
from app.logic.pipeline.anonimizador.anonimizar import AnonimizarTexto
from app.logic.pipeline.anonimizador.config import cargar_config
from app.logic.pipeline.base import Pipeline
from app.logic.pipeline.filtracion.embedder import Embedder
from app.logic.pipeline.filtracion.filtrar import FiltrarTexto
from app.logic.pipeline.filtracion.lista_blanca import cargar_lista_blanca
from app.logic.pipeline.limpieza.limpiar import LimpiarTexto
from app.logic.pipeline.limpieza.normalizar import NormalizarTexto
from app.logic.pipeline.out.guardar import GuardarTexto
from app.logic.pipeline.out.guardar_filtraciones import GuardarFiltraciones
from app.logic.pipeline.preprocesamiento.extraer import ExtraerTexto, crear_extractor


def construir_pipeline(extractor: str, segmentar: bool, modelo_embeddings: str) -> Pipeline:
    """Único lugar donde se decide qué etapas hay, en qué orden y con qué implementación.

    Se llama en cada tarea, así los cambios en los YAML aplican sin reiniciar el servidor.
    """
    config_anonimizacion = cargar_config(CONFIG_DIR / "anonimizacion.yaml")
    lista_blanca = cargar_lista_blanca(CONFIG_DIR / "lista_blanca.yaml")
    return Pipeline(etapas=[
        ExtraerTexto(crear_extractor(extractor)),
        LimpiarTexto(),                                               # solo espacios
        AnonimizarTexto(PresidioAnonimizador(config_anonimizacion)),
        NormalizarTexto(),                                            # minúsculas y tildes
        FiltrarTexto(lista_blanca, Embedder(MODELS_DIR, modelo_embeddings), segmentar, MODELS_DIR / "nltk_data"),
        GuardarTexto(),
        GuardarFiltraciones(),
    ])
