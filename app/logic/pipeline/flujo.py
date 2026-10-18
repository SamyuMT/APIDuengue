from app.core.rutas import CONFIG_DIR, MODELS_DIR
from app.logic.pipeline.anonimizador.anonimizador_presidio import PresidioAnonimizador
from app.logic.pipeline.anonimizador.anonimizar import AnonimizarTexto
from app.logic.pipeline.anonimizador.config import cargar_config
from app.logic.pipeline.base import Pipeline
from app.logic.pipeline.filtracion.embedder import Embedder
from app.logic.pipeline.filtracion.filtrar import FiltrarTexto
from app.logic.pipeline.filtracion.lista_blanca import cargar_lista_blanca
from app.logic.pipeline.indicador.calcular import CalcularIndicador
from app.logic.pipeline.indicador.config import cargar_indicador
from app.logic.pipeline.limpieza.limpiar import LimpiarTexto
from app.logic.pipeline.limpieza.normalizar import NormalizarTexto
from app.logic.pipeline.llm.config import cargar_evaluacion
from app.logic.pipeline.llm.enrutador import EnrutadorLLM
from app.logic.pipeline.llm.evaluar import EvaluarConLLM
from app.logic.pipeline.llm.validador import ValidadorRespuesta
from app.logic.pipeline.out.guardar import GuardarTexto
from app.logic.pipeline.out.guardar_evaluacion import GuardarEvaluacion
from app.logic.pipeline.out.guardar_filtraciones import GuardarFiltraciones
from app.logic.pipeline.out.guardar_indicador import GuardarIndicador
from app.logic.pipeline.preprocesamiento.extraer import ExtraerTexto, crear_extractor


def construir_pipeline(extractor: str, segmentar: bool, modelo_embeddings: str, modelo_llm: str | None) -> Pipeline:
    """Único lugar donde se decide qué etapas hay, en qué orden y con qué implementación.

    Se llama en cada tarea, así los cambios en los YAML aplican sin reiniciar el servidor.
    """
    config_anonimizacion = cargar_config(CONFIG_DIR / "anonimizacion.yaml")
    lista_blanca = cargar_lista_blanca(CONFIG_DIR / "lista_blanca.yaml")
    config_evaluacion, items_gpc = cargar_evaluacion(CONFIG_DIR)
    config_indicador = cargar_indicador(CONFIG_DIR / "indicador.yaml")
    return Pipeline(etapas=[
        ExtraerTexto(crear_extractor(extractor)),
        LimpiarTexto(),                                               # solo espacios
        AnonimizarTexto(PresidioAnonimizador(config_anonimizacion)),
        NormalizarTexto(),                                            # minúsculas y tildes
        FiltrarTexto(lista_blanca, Embedder(MODELS_DIR, modelo_embeddings), segmentar, MODELS_DIR / "nltk_data"),
        #GuardarTexto(),
        #GuardarFiltraciones(),
        EvaluarConLLM(
            items_gpc, EnrutadorLLM(modelo_llm, config_evaluacion), ValidadorRespuesta(config_evaluacion.validacion)
        ),
        #GuardarEvaluacion(),
        CalcularIndicador(config_indicador),
        #GuardarIndicador(),
    ])
