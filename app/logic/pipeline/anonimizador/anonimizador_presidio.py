import re
import threading
from collections import Counter
from functools import lru_cache

from app.logic.pipeline.anonimizador.anonimizador_base import Anonimizador, ResultadoAnonimizacion
from app.logic.pipeline.anonimizador.config import ConfigAnonimizacion

# Presidio y spaCy se importan dentro de las funciones: cargar el modelo tarda
# varios segundos y no debe ocurrir al arrancar el servidor, solo al anonimizar.

_SEGMENTO_DE_LINEA = re.compile(r"\S(?:[^\n]*\S)?")   # Tramo no vacío de una línea, sin espacios en los bordes


@lru_cache(maxsize=2)
def _motor_nlp(idioma: str, modelo: str):
    """El modelo spaCy se carga una sola vez y se reutiliza entre tareas."""
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    return NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": idioma, "model_name": modelo}],
    }).create_engine()


def _partir_por_linea(texto: str, detecciones: list) -> list:
    """spaCy puede detectar una entidad que cruza saltos de línea y se "come" etiquetas y renglones.

    Se parte cada detección en un tramo por línea: se anonimiza lo mismo, pero se conservan los saltos.
    """
    from presidio_analyzer import RecognizerResult

    partes = []
    for d in detecciones:
        for m in _SEGMENTO_DE_LINEA.finditer(texto, d.start, d.end):
            partes.append(RecognizerResult(d.entity_type, m.start(), m.end(), d.score))
    return partes


class PresidioAnonimizador(Anonimizador):
    """Adapta Microsoft Presidio (analyzer + anonymizer) a la interfaz Anonimizador."""

    def __init__(self, config: ConfigAnonimizacion):
        self.config = config
        self._motores = None
        self._lock = threading.Lock()   # Dos documentos en paralelo no deben construirlo dos veces

    def anonimizar(self, texto: str) -> ResultadoAnonimizacion:
        from presidio_anonymizer.entities import OperatorConfig

        analizador, anonimizador = self._obtener_motores()
        entidades = self.config.entidades_a_anonimizar
        detecciones = analizador.analyze(
            text=texto,
            language=self.config.idioma,
            entities=list(entidades),
            score_threshold=self.config.umbral,
        )
        resultado = anonimizador.anonymize(
            text=texto,
            analyzer_results=_partir_por_linea(texto, detecciones),
            operators={
                nombre: OperatorConfig("replace", {"new_value": e.etiqueta})
                for nombre, e in entidades.items()
            },
        )
        conteo = Counter(item.entity_type for item in resultado.items)
        return ResultadoAnonimizacion(texto=resultado.text, conteo=dict(conteo))

    def _obtener_motores(self):
        with self._lock:
            if self._motores is None:
                self._motores = self._crear_motores()
        return self._motores

    def _crear_motores(self):
        from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
        from presidio_anonymizer import AnonymizerEngine

        idioma = self.config.idioma
        nlp = _motor_nlp(idioma, self.config.modelo_spacy)

        registro = RecognizerRegistry(supported_languages=[idioma])
        registro.load_predefined_recognizers(nlp_engine=nlp, languages=[idioma])
        for nombre, entidad in self.config.entidades.items():
            if entidad.patrones:
                registro.add_recognizer(PatternRecognizer(
                    supported_entity=nombre,
                    name=f"reconocedor_{nombre.lower()}",
                    patterns=[Pattern(name=p.nombre, regex=p.regex, score=p.score) for p in entidad.patrones],
                    supported_language=idioma,
                ))

        analizador = AnalyzerEngine(nlp_engine=nlp, registry=registro, supported_languages=[idioma])
        return analizador, AnonymizerEngine()
