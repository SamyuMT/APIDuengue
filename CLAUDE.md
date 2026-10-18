# CLAUDE.md

Guía para Claude (y cualquier colaborador) sobre este proyecto: cómo está construido, cómo se trabaja
y **por dónde va el desarrollo**. Actualizar la sección "Estado" al terminar cada avance.

## Qué es

API FastAPI (tesis de maestría) que procesa lotes de historias clínicas (HC) en PDF y calcula su
adherencia a la GPC de dengue. Pipeline por documento (activo en `flujo.py`):

```
extraer → limpiar → anonimizar → normalizar → filtrar → evaluar_llm → calcular_indicador
```
Al finalizar la tarea: reporte consolidado `reporte_adherencia.xlsx` / `.json`.

Las etapas de guardado por HC (`guardar`, `guardar_filtraciones`, `guardar_evaluacion`,
`guardar_indicador`) existen en `pipeline/out/` pero **el usuario las dejó comentadas** en `flujo.py`.

Además, un servicio LLM independiente (`/v1/llm`): vincular modelos, consulta única y chat.

Repositorio: https://github.com/SamyuMT/APIDuengue

## Cómo trabaja el usuario (respetar)

- **Ir de a poco**: un servicio / una etapa a la vez. No generar módulos que no se pidieron.
- **Código limpio y simple**, nombres y comentarios en español, como el código existente.
- Antes de implementar algo nuevo, el usuario suele tener un **notebook de referencia** en
  `D:\TrabajosPosgrado\ProyectoGrado\DesarrolloSoftware\PruebasSeleccionTecnicas\<tema>\`. Leerlo y
  reproducir su comportamiento (verificar contra sus salidas cuando existan).
- Proyecto de referencia (más complejo, no copiar su complejidad):
  `D:\TrabajosPosgrado\ProyectoGrado\DesarrolloSoftware\proyectGrado\gpc-dengue\backend`.
- Configuración editable por humanos → **YAML** en `config/` (validado con Pydantic al cargar).
  Datos generados por el programa → JSON.
- Modelos → `models/<nombre>`; nada se descarga en tiempo de ejecución (objetivo: Docker / .exe).
- Cuando solo pregunta ("solo dime", "pregunta"), responder sin modificar código.

## Arquitectura

```
app/api/routes/<servicio>.py   HTTP: valida, llama al servicio, traduce errores a códigos HTTP
app/service/<servicio>.py      Clase con funciones async; orquesta
app/logic/                     Lógica pura (sin FastAPI)
app/logic/llm/                 Núcleo LLM compartido (registro de modelos, clientes, chats)
app/logic/pipeline/            Etapas; flujo.py es el ÚNICO lugar donde se arma el pipeline
app/schemas/                   Modelos Pydantic (request/response/checkpoint)
app/core/rutas.py              RAIZ, CONFIG_DIR, MODELS_DIR, DATA_DIR
config/                        anonimizacion, lista_blanca, evaluacion_llm, prompts/, indicador (YAML)
```

Reglas del pipeline:
- Cada etapa hereda de `Etapa` (`base.py`), tiene `nombre` y `ejecutar(ctx) -> ctx`. Es **síncrona**:
  el servicio la ejecuta en un hilo.
- Los datos viajan en `Contexto` (`base.py`), agrupados por la etapa que los llena. Las etapas leen del
  `Contexto` en memoria, **nunca** de los archivos guardados (p. ej. `evaluar_llm` usa `ctx.filtraciones`).
- Si hay varias implementaciones intercambiables → **Adapter**: `*_base.py` (interfaz + dataclass de
  resultado), un archivo por adaptador, y la etapa recibe la interfaz (inyección en `flujo.py`).
  Ej.: `preprocesamiento/` (PyMuPDF/pdfplumber), `anonimizador/` (Presidio), `logic/llm/` (clientes).
- Librerías pesadas (spaCy, Presidio, sentence-transformers, openai) se importan **dentro** de las
  funciones y el modelo se carga una sola vez (caché + lock): el servidor arranca rápido.
- Anonimizar reemplaza `ctx.texto`: después de esa etapa el texto original ya no existe.
- `flujo.py` relee todos los YAML en cada tarea: los cambios aplican sin reiniciar.

Tareas (`tarea_service.py` + `tarea_logic.py`):
- `asyncio.create_task` por tarea; semáforo **global** de 2 documentos en paralelo.
- Checkpoint `data/tareas/<id>.json` tras cada documento (escritura atómica). Reanudar = procesar todo
  documento no `completado` (desde el inicio del pipeline; no hay checkpoint por etapa).
- Parámetros en el checkpoint: `extractor`, `segmentar`, `modelo_embeddings`, `modelo_llm`. Resultado por
  HC en `DocumentoTarea.indicador`; rutas del reporte en `Tarea.reportes`.
- Detener es cooperativo: se verifica entre etapas (`marcar_etapa`).
- Al finalizar: `tarea_logic.generar_reporte` → `pipeline/indicador/reporte.py` con las HC completadas.

LLM:
- `app/logic/llm/`: `registro.py` (modelos vinculados en `data/llm/modelos.json`), `cliente_base.py` +
  `cliente_openai.py` (un solo tipo `openai_compatible`: OpenAI, DeepSeek, Gemini, Anthropic, LM Studio,
  Ollama vía `base_url`), `chats.py` (`data/llm/chats/`, fuera de git).
- **Las llaves nunca van al registro**: solo el nombre de la variable (`api_key_env`); el valor va al `.env`.
- El servicio HTTP (`llm_service.py`) y el pipeline (`pipeline/llm/`) usan ese mismo núcleo.
- `pipeline/llm/`:
  - `config.py`: `config/evaluacion_llm.yaml` + prompts (`config/prompts/gpc_v2.yaml`).
  - `enrutador.py`: modelo principal → resto de vinculados; reintentos propios con espera exponencial
    + `circuit_breaker.py` por modelo (global, compartido entre documentos y tareas).
  - `validador.py`: la respuesta COMPLETA normalizada debe ser SI/NO/PARCIAL o un alias ("PARC");
    si no, pide corrección con el historial hasta 2 veces; luego `NO` con `valida: false`.
  - `bitacora.py`: cada intento (ok / error / omitido_circuito_abierto / respuesta_invalida) se escribe
    al momento en `<carpeta_salida>/<tarea_id>/llm_intentos.jsonl` (sin prompt ni texto clínico).
  - `evaluar.py`: etapa; si fallan todos los modelos en un ítem → `motivo: todos_fallaron` y sigue.
- `pipeline/indicador/`: `config.py` (`config/indicador.yaml`), `calculo.py` (puro), `calcular.py`
  (etapa), `reporte.py` (Excel + JSON consolidados).

## Comandos

```bash
.venv\Scripts\python.exe -m uvicorn app.main:app --reload      # API en http://127.0.0.1:8000/docs
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Para pruebas sin levantar servidor: `fastapi.testclient.TestClient` con `PYTHONPATH=.`, apuntando
`tarea_logic.CHECKPOINT_DIR`, `registro.REGISTRO`/`registro.ENV` y `chats.CHATS_DIR` a una carpeta
temporal, y reemplazando `cliente_openai.CLIENTES["openai_compatible"]` por un cliente falso.

## Cuidados

- **Datos clínicos**: nunca imprimir contenido de historias clínicas ni valores personales en la salida;
  verificar fugas comparando valores sin mostrarlos (enmascarar letras/dígitos).
- **Puerto 8000**: el usuario suele tener su propio `uvicorn --reload` corriendo. Comprobarlo antes de
  levantar otro servidor; para probar, preferir TestClient en proceso.
- **No lanzar lotes largos** (45 PDF ≈ 15 min) ni consultas a proveedores LLM reales (cuestan dinero)
  sin que el usuario lo pida; probar con 1 PDF y cliente falso.
- **YAML**: `NO` sin comillas es el booleano `false` (como valor y como clave). Escribir siempre `"NO"`.
- **Smart App Control (Windows)** bloquea a veces DLL sin firmar al importar (`thinc`, `torch`). Se
  resuelve con `pip install --force-reinstall --no-deps <paquete>`. No cambiar la configuración de
  seguridad del sistema.
- `models/`, `.env`, `.venv`, `data/llm/chats/` no se versionan. El usuario decidió versionar `tests/` y `data/`.

## Estado (2026-10-18)

### Hecho
- **API base** por capas. Servicio `documents` (`POST /v1/documents/list`).
- **Servicio `tareas`**: crear (202 + id), consultar progreso y etapa en vivo, `pendientes`,
  `en-ejecucion` (desde memoria: progreso, `en_curso` archivo→etapa, `deteniendo`), reanudar, detener
  (`detenida`), eliminar (solo si no corre; borra solo el checkpoint). `interrumpida` si el servidor cayó.
- **Etapas**:
  - **extraer**: Adapter PyMuPDF / pdfplumber (`extractor`).
  - **limpiar**: solo espacios (antes de anonimizar).
  - **anonimizar**: Presidio + spaCy `es_core_news_lg` + regex en `config/anonimizacion.yaml`; las
    detecciones que cruzan saltos de línea se parten por línea.
  - **normalizar**: minúsculas, sin tildes; conserva etiquetas `<...>`, fechas, `/ % ° ( ) + -`.
  - **filtrar**: sentence-transformers (`models/<modelo_embeddings>`) contra `config/lista_blanca.yaml`,
    `segmentar` (NLTK, `models/nltk_data`) o por líneas → `ctx.filtraciones` (5 categorías).
    Reproduce exactamente los 4 JSON del notebook `PruebasSeleccionTecnicas/filtracion`.
  - **evaluar_llm**: 53 ítems con grupo (28–30 sin grupo se omiten); `sin_contenido` si el grupo no
    tiene texto; enrutador + circuit breaker + validador + bitácora.
  - **calcular_indicador**: códigos NO=0/SI=1/PARCIAL=2; puntaje SI=5, PARCIAL=5 (configurable), NO=1;
    sin respuesta = NO. Módulo = promedio de sus ítems; macro: evaluación general, diagnóstico,
    manejo (= promedio de ambulatorio, hospitalario y UCI; el auditor/front filtra según dónde estuvo
    el paciente); total = promedio de los macro. Ítems 14, 24, 25 no califican; ítem 14 = NO anula
    17 y 18. Niveles BAJO < 3, MEDIO 3 a < 4, ALTO ≥ 4.
  - **Reporte** al finalizar: `reporte_adherencia.xlsx` (hoja *Por HC*: códigos por ítem + 7
    calificaciones + 4 niveles; hoja *General*: promedio y nivel) y `reporte_adherencia.json`
    (`general`, `niveles_general`, `por_hc`).
- **Servicio LLM**: `GET/POST/DELETE /v1/llm/modelos`, `POST /v1/llm/consulta`, `POST /v1/llm/chats`,
  `POST /v1/llm/chats/{id}/mensajes`, `GET /v1/llm/chats/{id}`.
- **Probado de punta a punta con un proveedor real (DeepSeek `deepseek-chat`)**: 2 HC, 106 consultas
  `ok`, reporte generado. El circuit breaker con un modelo caído (`falla`, puerto local cerrado) lo
  probó el usuario.
- Tiempos por documento: extraer 0,1 s (PyMuPDF) / 8 s (pdfplumber), anonimizar ≈ 21–27 s
  (+ ≈ 37 s de carga del modelo la primera vez), filtrar ≈ 5 s con segmentación, evaluar ≈ 53 consultas.
- Repositorio en GitHub: commit `primerAvance` (todo lo posterior está **sin commit**).

### Pendiente — consecuencias de comentar las etapas de guardado
- [ ] Con `guardar_evaluacion` comentada **se perdió la protección de `todos_fallaron`**: esa etapa marcaba
      el documento con error para reanudarlo. Ahora, si un proveedor cae, esos ítems llegan sin respuesta
      a `calcular_indicador`, que los cuenta como NO **sin avisar**. Mover esa verificación a
      `evaluar_llm` o `calcular_indicador`, o volver a activar `guardar_evaluacion`.
- [ ] Sin `guardar_*` no quedan por HC el texto anonimizado, el filtrado, las respuestas del LLM
      (con `respuesta_cruda`, `valida`, tokens) ni el indicador en archivo: solo el reporte consolidado,
      la bitácora y `DocumentoTarea.indicador` en el checkpoint. Decidir qué guardar (¿opción por tarea?).

### Pendiente — calidad
- [ ] **Sobre-anonimización**: spaCy marca rótulos y términos ("Estado civil", "Ocupación", sexo) como
      `<UBICACION>`/`<NOMBRE>` (823 y 520 en una HC). Lista blanca médica para no anonimizarlos.
- [ ] **Fuga del nombre de la EPS**: el patrón `eps` toma "EPS SAS" pero no el nombre previo →
      diccionario de EPS (ver `config/dictionaries/` en gpc-dengue).
- [ ] Guardar `ctx.entidades_anonimizadas` en `DocumentoTarea` (hoy se calcula y se pierde).
- [ ] Filtrado: probar modelo multilingüe (`paraphrase-multilingual-MiniLM-L12-v2`); `all-MiniLM-L6-v2`
      es solo inglés. Evaluar orden por documento en vez de por score. Ajustar `umbral`.
- [ ] Validar el indicador contra evaluaciones manuales de auditores (el Excel de ejemplo con códigos 0/1/2).

### Pendiente — funcionalidad
- [ ] Endpoint para regenerar el reporte de una tarea (p. ej. tras cambiar `indicador.yaml`).
- [ ] Endpoint para descargar el reporte (Excel/JSON) de una tarea.
- [ ] Exponer el estado de los circuit breakers (p. ej. `GET /v1/llm/circuitos`).
- [ ] Paralelismo entre tareas: el semáforo de 2 documentos es global (dos tareas se reparten 2 cupos).
      Para tareas realmente en paralelo: semáforo por tarea + límite global, configurable.
- [ ] Checkpoint por etapa: hoy reanudar repite extracción, anonimización, filtrado y las 53 consultas.

### Pendiente — infraestructura
- [ ] Mover `es_core_news_lg` a `models/` (cargar por ruta desde el YAML).
- [ ] Fijar versiones exactas (`requirements.lock`).
- [ ] Empaquetado: Docker (recomendado) o .exe (requiere firma de código por Smart App Control).
- [ ] Pruebas automáticas (pytest) por etapa y endpoints (hoy hay scripts manuales de prueba).
- [ ] Configuración por `.env` con `pydantic-settings` (paralelismo, rutas) y logging estructurado.
- [ ] Rendimiento de la anonimización (cuello de botella).
- [ ] Costo: ~53 consultas de ~8.800 tokens por HC (~470 k tokens); las correcciones del validador
      reenvían el prompt completo.
- [ ] Hacer commit/push del avance (todo lo posterior a `primerAvance`).
