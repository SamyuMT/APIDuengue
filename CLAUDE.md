# CLAUDE.md — APIDuengue

Contexto completo para cualquier Claude (o persona) que retome este proyecto: qué es, cómo está hecho,
cómo trabaja el usuario, qué NO tocar, qué SÍ falta y cómo extenderlo. **Actualizar la sección
"Estado" al terminar cada avance.**

---

## 1. Qué es

Herramienta de tesis de maestría: una **API FastAPI** que procesa lotes de historias clínicas (HC) en
PDF y calcula su **adherencia a la Guía de Práctica Clínica (GPC) de dengue**, replicando el formato
de evaluación de los auditores (ítems con respuesta SI / NO / PARCIAL → calificación 1–5 → nivel).

Por cada HC (pipeline activo en `app/logic/pipeline/flujo.py`):

```
extraer → limpiar → anonimizar → normalizar → filtrar → evaluar_llm → calcular_indicador
```

Al terminar la tarea (lote): `reporte_adherencia.xlsx` + `reporte_adherencia.json`.
Además hay un **servicio LLM independiente** (`/v1/llm`): vincular modelos, consulta única y chat.

Objetivo final: empaquetarlo (Docker recomendado, o .exe) con todos los modelos dentro, sin descargar
nada al ejecutar, y consumirlo desde un **frontend** (carpeta hermana `../frontend`, hoy vacía).

## 2. Ubicaciones

| Qué | Dónde |
|---|---|
| Repositorio (este) | `D:\ProyectoGradoMaestria\APIDuengue` → https://github.com/SamyuMT/APIDuengue (rama `main`) |
| Frontend (React 18 + TS + Vite, pantalla inicial) | `D:\ProyectoGradoMaestria\frontend` — `npm run dev` → http://localhost:5173; proxy `/v1` → `127.0.0.1:8000` (sin CORS en desarrollo). No es repo git todavía |
| Notebooks de referencia del usuario | `D:\TrabajosPosgrado\ProyectoGrado\DesarrolloSoftware\PruebasSeleccionTecnicas\<tema>\` (`Anonimizacion`, `filtracion`, `LLM`, `models`) |
| Proyecto de referencia antiguo (NO copiar su complejidad) | `D:\TrabajosPosgrado\ProyectoGrado\DesarrolloSoftware\proyectGrado\gpc-dengue\backend` |
| PDFs de prueba | `tests/aprocesar/` (HC de prueba; se versionan por decisión del usuario) |

## 3. Cómo trabaja el usuario (respetar siempre)

- **Ir de a poco**: un servicio o una etapa a la vez. No crear módulos, endpoints ni archivos que no pidió.
- **Código limpio y simple**, en español (nombres, comentarios, mensajes), igual que el existente.
- **Granular**: una responsabilidad por archivo `.py`; carpetas por módulo del pipeline.
- Antes de implementar algo nuevo suele haber un **notebook de referencia**: leerlo, reproducir su
  comportamiento y **verificar contra sus salidas** cuando existan.
- Configuración editable por humanos → **YAML** en `config/`, validado con Pydantic al cargar.
  Datos que genera el programa → **JSON**.
- Modelos → `models/<nombre>`. Nada se descarga en tiempo de ejecución.
- Cuando dice "pregunta", "solo dime" o "no lo hagas": **responder sin modificar código**.
- Cuando pide cambios: implementarlos, probarlos (ver §10) y actualizar este archivo y el README.
- Le gusta que se le **cuestione** cuando algo no es buena práctica (p. ej. patrones de diseño).
- Hace él mismo los commits/push salvo que lo pida; los mensajes de commit los elige él.

## 4. Arquitectura

```
app/
├── main.py                  # create_app(): carga .env, incluye routers con prefijo /v1
├── api/router.py            # junta documents, tareas, llm
├── api/routes/<servicio>.py # HTTP: valida, llama al servicio, traduce excepciones → códigos HTTP
├── service/<servicio>.py    # Clase con métodos async; orquesta; lo pesado va con asyncio.to_thread
├── schemas/                 # Pydantic: requests, responses y checkpoint (documents, tareas, llm)
├── core/rutas.py            # RAIZ, CONFIG_DIR, MODELS_DIR, DATA_DIR
└── logic/                   # Lógica pura, sin FastAPI
    ├── document_logic.py    # validate_folder, find_pdfs
    ├── tarea_logic.py       # crear tarea, checkpoint (JSON atómico), progreso, finalizar, generar_reporte
    ├── llm/                 # NÚCLEO LLM compartido por el servicio /v1/llm y el pipeline
    │   ├── registro.py      # modelos vinculados (data/llm/modelos.json); llaves → .env
    │   ├── cliente_base.py  # interfaz ClienteLLM (Adapter)
    │   ├── cliente_openai.py# adaptador openai_compatible + CLIENTES + completar()
    │   └── chats.py         # chats persistidos en data/llm/chats/ (fuera de git)
    └── pipeline/
        ├── base.py          # Contexto (dataclass), Etapa (ABC), Pipeline, ErrorEtapa
        ├── flujo.py         # ÚNICO lugar donde se arma el pipeline (qué etapas, orden, implementación)
        ├── preprocesamiento/# extractor_base, extractor_pymupdf, extractor_pdfplumber, extraer (etapa + crear_extractor)
        ├── limpieza/        # limpiar (solo espacios), normalizar (minúsculas/tildes)
        ├── anonimizador/    # anonimizador_base, config (YAML), anonimizador_presidio, anonimizar (etapa)
        ├── filtracion/      # lista_blanca, segmentador, embedder, similitud, filtrar (etapa)
        ├── llm/             # config, enrutador, circuit_breaker, validador, bitacora, evaluar (etapa)
        ├── indicador/       # config, calculo (puro), calcular (etapa), reporte (Excel + JSON)
        └── out/             # guardar, guardar_filtraciones, guardar_evaluacion, guardar_indicador
config/                      # YAML editables (ver §8)
models/                      # all-MiniLM-L6-v2/, nltk_data/ (NO se versiona)
data/tareas/                 # checkpoints de tareas
data/llm/                    # modelos.json (versionado, sin llaves) y chats/ (no versionado)
tests/                       # aprocesar/ (PDFs), resultados/ (salidas de corridas)
```

### Reglas del pipeline (no romperlas)

- Cada etapa hereda de `Etapa`, tiene `nombre` y `ejecutar(ctx) -> ctx`. Es **síncrona**: el servicio
  corre `pipeline.ejecutar` en un hilo (`asyncio.to_thread`).
- Los datos viajan en `Contexto` (`base.py`), agrupados por la etapa que los llena. **Las etapas leen
  del `Contexto` en memoria, nunca de los archivos guardados** (p. ej. `evaluar_llm` usa
  `ctx.filtraciones`, no `_filtrado.json`).
- Implementaciones intercambiables → **Adapter**: `*_base.py` (interfaz + dataclass de resultado), un
  archivo por adaptador, la etapa recibe la interfaz y la inyección se hace en `flujo.py`.
- Librerías pesadas (spaCy, Presidio, sentence-transformers, torch, openai) se importan **dentro de
  las funciones**; los modelos se cargan una sola vez (caché + `threading.Lock`). El servidor arranca rápido.
- **Anonimizar reemplaza `ctx.texto`**: después de esa etapa el texto original ya no existe.
- `construir_pipeline` se llama en cada tarea y relee todos los YAML: los cambios aplican sin reiniciar.
  También se llama al crear `TareaService` **solo para obtener los nombres de las etapas**
  (`construir_pipeline("pymupdf", True, MODELO_EMBEDDINGS, None)`): no debe cargar modelos al construirse.

### Contexto (qué llena cada etapa)

| Campo | Lo llena |
|---|---|
| `doc_id`, `ruta_pdf`, `carpeta_salida` | servicio de tareas |
| `num_paginas`, `texto` | extraer (luego limpiar / anonimizar / normalizar modifican `texto`) |
| `entidades_anonimizadas` | anonimizar (conteo por tipo, nunca valores) |
| `filtraciones` | filtrar → `{categoria: texto}` con las 5 categorías |
| `evaluaciones` | evaluar_llm → lista, un dict por ítem |
| `indicador` | calcular_indicador → `{items, modulos, indicadores, niveles}` |
| `tiempos` | Pipeline (segundos por etapa) |

## 5. Servicio de tareas

- `asyncio.create_task` por tarea; **semáforo global** de 2 documentos en paralelo (compartido entre tareas).
- Checkpoint `data/tareas/<id>.json` tras cada documento (escritura atómica `.tmp` → `replace`).
- Reanudar = procesar todo documento no `completado`, **desde el inicio del pipeline** (no hay
  checkpoint por etapa).
- En el checkpoint (`schemas/tareas.py: Tarea`): carpetas, documentos (`DocumentoTarea`: estado, etapa,
  error, tiempos, **indicador**), parámetros (`extractor`, `segmentar`, `modelo_embeddings`,
  `modelo_llm`), `resumen`, `reportes` (rutas del Excel/JSON).
- Estados de tarea: `en_ejecucion`, `completada`, `completada_con_errores`, `detenida`, `interrumpida`
  (calculado: checkpoint dice en_ejecucion pero no corre), `error`.
- Estados de documento: `pendiente`, `en_proceso`, `completado`, `error` (`etapa` = donde falló).
- **Detener es cooperativo**: `marcar_etapa` lanza `_DetencionSolicitada` entre etapas; el documento
  vuelve a `pendiente`. No interrumpe una etapa en curso (evaluar_llm puede tardar minutos).
- Al finalizar (no al detener): `tarea_logic.generar_reporte` con las HC completadas → `Tarea.reportes`.

| Método | Ruta | Notas |
|---|---|---|
| POST | `/v1/documents/list` | `{folder}` → `{total, files}` |
| POST | `/v1/tareas` | `{carpeta_entrada, carpeta_salida, extractor, segmentar, modelo_embeddings, modelo_llm}` → 202 `{tarea_id}`; 400 si carpeta/modelo inválido |
| GET | `/v1/tareas/pendientes` | ids no completadas y no activas (reanudables) |
| GET | `/v1/tareas/en-ejecucion` | desde memoria: progreso, `en_curso` archivo→etapa, `deteniendo` |
| GET | `/v1/tareas/{id}` | checkpoint + progreso + etapas |
| POST | `/v1/tareas/{id}/reanudar` | 409 si ya corre |
| POST | `/v1/tareas/{id}/detener` | 202; 409 si no corre |
| DELETE | `/v1/tareas/{id}` | 204; solo si no corre; borra solo el checkpoint (no los resultados) |

Rutas fijas (`/pendientes`, `/en-ejecucion`) **deben declararse antes** de `/{tarea_id}` en el router.

## 6. LLM

### Servicio `/v1/llm` (independiente del pipeline)

| Método | Ruta | Notas |
|---|---|---|
| GET | `/v1/llm/modelos` | sin llaves; `api_key_configurada` |
| POST | `/v1/llm/modelos` | `{nombre, modelo, base_url, api_key_env, api_key?, timeout_s}`; si trae `api_key` se escribe en `.env` |
| DELETE | `/v1/llm/modelos/{nombre}` | |
| POST | `/v1/llm/consulta` | `{modelo, prompt, system?, temperatura, max_tokens, formato_json}` |
| POST | `/v1/llm/chats` → `/chats/{id}/mensajes` → GET `/chats/{id}` | el modelo recibe todo el historial |

- Un solo adaptador `openai_compatible`: cualquier proveedor cambiando `base_url` (OpenAI, **DeepSeek**
  `https://api.deepseek.com` + `deepseek-chat`, Gemini, Anthropic, LM Studio, Ollama).
- **Las llaves nunca van a `data/llm/modelos.json`**: solo el nombre de la variable (`api_key_env`).
- Errores: 404 modelo/chat inexistente, 502 el proveedor falló.

### En el pipeline (`pipeline/llm/`)

- `config.py`: `config/evaluacion_llm.yaml` + prompts (`archivo_prompts: prompts/gpc_v2.yaml`).
  56 ítems; 53 con `grupo_evaluacion` (= categoría de `ctx.filtraciones`); 28–30 sin grupo → se omiten.
- `enrutador.py`: modelo principal de la tarea primero, luego el resto de vinculados. Por modelo:
  reintentos propios con espera exponencial; al agotarlos cuenta un fallo en su `CircuitBreaker`
  (`circuit_breaker.py`, **global por modelo**, compartido entre documentos y tareas; cerrado →
  abierto tras N fallos → semiabierto tras `segundos_abierto`). Si nadie responde: `TodosLosModelosFallaron`.
- `validador.py`: la respuesta **completa** normalizada (mayúsculas, sin tildes ni puntuación) debe ser
  una opción o alias (`PARC` → PARCIAL). Si no: mensaje de corrección con el historial, hasta
  `reintentos` (2); luego `por_defecto` (NO) con `valida: false`, `motivo: respuesta_invalida`.
  "No estoy seguro" **no** cuenta como NO (regla estricta a propósito).
- `bitacora.py`: cada intento (`ok`, `error`, `omitido_circuito_abierto`, `respuesta_invalida`) se
  escribe **al momento** en `<carpeta_salida>/<tarea_id>/llm_intentos.jsonl` (sin prompt ni texto clínico;
  `respuesta_cruda` máx. 200 caracteres).
- `evaluar.py` (etapa): si el grupo no tiene texto → `motivo: sin_contenido` sin consultar; si fallan
  todos los modelos → `motivo: todos_fallaron` y sigue con el siguiente ítem.

## 7. Indicador de adherencia (`pipeline/indicador/`, `config/indicador.yaml`)

| Respuesta | Código (Excel) | Puntaje |
|---|---|---|
| NO | 0 | 1 |
| SI | 1 | 5 |
| PARCIAL | 2 | 5 (configurable a futuro) |

- Sin respuesta (`sin_contenido`) = `sin_respuesta` (NO).
- Módulo = promedio de sus ítems que califican. Macro: `evaluacion_general`, `diagnostico`,
  `manejo` (= promedio de ambulatorio, hospitalario y UCI). Total = promedio de los macro.
- Ítems 14, 24, 25 no califican (se reportan). Ítem 14 = NO anula 17 y 18.
- Niveles: BAJO < 3, MEDIO 3 a < 4, ALTO ≥ 4.
- **Decisión del usuario**: manejo promedia los 3 submódulos aunque al paciente solo aplique uno; el
  auditor / el frontend filtra según dónde estuvo el paciente. No "arreglar" eso.
- El "nivel de apropiación de la IPS" del formato original se omite a propósito.
- Excel (`reporte.py`): hoja *Por HC* = `Historia clínica` + `item N` (códigos 0/1/2) + 7 calificaciones
  (5 módulos, Manejo, Calificación total) + 4 niveles (macro + total); hoja *General* = promedio y nivel.
  JSON: `total_hc`, `general`, `niveles_general`, `por_hc`.

## 8. Configuración (`config/`)

| Archivo | Qué controla |
|---|---|
| `anonimizacion.yaml` | modelo spaCy, umbral, entidades: `anonimizar`, `etiqueta`, `patrones` (regex `(?ix)`, usar `[ \t]` y no `\s`) |
| `lista_blanca.yaml` | `umbral` (0.5) y categoría → subcategoría → términos (generada desde el notebook) |
| `evaluacion_llm.yaml` | `archivo_prompts`, `generacion` (temperatura 0, max_tokens 5), `reintentos`, `circuit_breaker`, `validacion` |
| `prompts/gpc_v1.yaml`, `gpc_v2.yaml` | prompts por ítem con `{contenido}` (idénticos a los JSON del notebook) |
| `indicador.yaml` | códigos, puntajes, sin_respuesta, módulos (orden de columnas), macro, niveles, excluir, condicionales |

**Trampa de YAML**: `NO` sin comillas es el booleano `false`, como valor **y como clave**. Escribir
siempre `"NO"`. Ya rompió el arranque de la app una vez.

## 9. Qué NO tocar (verificado o decidido por el usuario)

- **Orden limpiar → anonimizar → normalizar.** Normalizar antes de anonimizar destruye fechas (`/`),
  direcciones (`#`, `-`), mayúsculas que usa spaCy y hace que las fechas clínicas se lean como ids.
- **Algoritmo de filtrado** (`filtracion/`): reproduce **exactamente** los 4 JSON del notebook
  (`PruebasSeleccionTecnicas/filtracion/Historia_filtrada_*2.json`). Cualquier cambio (orden por
  documento, normalizar la lista blanca) cambia resultados: solo si el usuario lo pide, y volver a comparar.
- **Prompts y lista blanca**: son copia fiel de los del usuario; no reescribirlos.
- **Llaves fuera del registro y del repo**: `.env`, `models/`, `.venv`, `data/llm/chats/` no se versionan.
- **Regla estricta del validador** (respuesta completa) y la marca `valida: false`: el usuario necesita
  distinguir NO reales de NO por defecto.
- **Reglas del indicador** (§7) confirmadas por el usuario.
- **Compatibilidad del checkpoint**: todo campo nuevo en `Tarea`/`DocumentoTarea` debe tener valor por
  defecto (hay checkpoints viejos que deben seguir cargando).
- **Etapas `guardar_*` comentadas en `flujo.py`**: las comentó el usuario. No reactivarlas sin preguntar
  (ver pendiente P1 sobre sus consecuencias).
- `app/logic/pipeline/preprocesamiento/extraer.py` y `extractor_pymupdf.py` tienen comentarios del
  usuario: respetarlos.

## 10. Cómo probar

- **No** levantar `uvicorn` sin revisar el puerto 8000: el usuario suele tener su propio
  `uvicorn --reload` corriendo (una vez se creó una tarea de 45 PDF en su servidor por error).
  Preferir `fastapi.testclient.TestClient` dentro del proceso.
- Aislar datos: apuntar `tarea_logic.CHECKPOINT_DIR`, `registro.REGISTRO`, `registro.ENV` y
  `chats.CHATS_DIR` a una carpeta temporal (scratchpad). Nunca ensuciar `data/` ni el `.env`.
- LLM falso: reemplazar `cliente_openai.CLIENTES["openai_compatible"]` por un objeto con
  `completar(modelo, mensajes, **kw) -> RespuestaLLM`. Modelo que falla de verdad sin salir a internet:
  `base_url: http://127.0.0.1:9/v1`.
- Pipeline lento falso: reemplazar `app.service.tarea_service.construir_pipeline` por un `Pipeline` de
  etapas con `time.sleep`.
- **No** hacer consultas a proveedores reales (cuestan dinero) ni lotes largos (45 PDF ≈ 15 min+)
  sin que el usuario lo pida. Probar con 1 PDF.
- Scripts de prueba: en el scratchpad de la sesión (no hay pytest todavía).
- Comandos:
  ```bash
  .venv\Scripts\python.exe -m uvicorn app.main:app --reload     # http://127.0.0.1:8000/docs
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  ```
  Para scripts: `PYTHONPATH=.` desde la raíz del repo.

## 11. Cómo extender (recetas)

- **Nueva etapa**: archivo en la carpeta del módulo, clase que hereda de `Etapa` con `nombre` único;
  si produce datos, campo nuevo en `Contexto` con default; agregarla en `flujo.py`.
- **Nuevo extractor PDF**: adaptador que herede de `ExtractorPdf` + entrada en `EXTRACTORES` (`extraer.py`).
- **Nuevo motor de anonimización**: heredar de `Anonimizador` (`anonimizador_base.py`) e inyectarlo en `flujo.py`.
- **Nuevo modelo de embeddings**: copiarlo a `models/<nombre>` (debe tener `modules.json`) y enviar
  `modelo_embeddings: "<nombre>"` al crear la tarea. Sugerido: `paraphrase-multilingual-MiniLM-L12-v2`.
- **Nuevo proveedor LLM**: `POST /v1/llm/modelos` con su `base_url`. Solo si no es compatible con
  OpenAI: nuevo adaptador `ClienteLLM` + entrada en `CLIENTES` + valor en `ModeloLLM.tipo`.
- **Cambiar prompts / versión**: `archivo_prompts` en `evaluacion_llm.yaml`.
- **Cambiar puntajes, niveles o reglas**: `indicador.yaml` (se valida al cargar).
- **Nuevo endpoint**: ruta en `routes/`, método async en el servicio, lógica en `logic/`, schemas en `schemas/`.

## 12. Cuidados

- **Datos clínicos**: nunca imprimir contenido de HC ni valores personales. Para verificar fugas,
  comparar valores sin mostrarlos (enmascarar letras → `x`, dígitos → `9`).
- **Smart App Control (Windows)** bloquea a veces DLL sin firmar al importar (`thinc`, `torch`):
  `pip install --force-reinstall --no-deps <paquete>`. No cambiar la configuración de seguridad.
- El usuario versiona `tests/` y `data/` (incluye PDFs de HC de prueba); fue su decisión.
- La llave de DeepSeek se pegó una vez en el chat: se le recomendó rotarla.
- Enviar HC (aunque anonimizadas) a proveedores externos implica consideraciones éticas de la tesis.

## 13. Estado (2026-10-21)

### Hecho y probado
- API por capas; servicios `documents`, `tareas`, `llm`.
- Tareas: crear, progreso en vivo, pendientes, en ejecución, reanudar, detener, eliminar, interrumpida.
- Pipeline completo: extraer (PyMuPDF/pdfplumber), limpiar, anonimizar (Presidio + spaCy + YAML),
  normalizar, filtrar (verificado = notebook), evaluar_llm (enrutador + circuit breaker + validador +
  bitácora), calcular_indicador, reporte Excel/JSON.
- **Corrida real de punta a punta con DeepSeek**: 2 HC, 106 consultas ok, reporte generado.
- Circuit breaker con modelo caído probado por el usuario.
- Tiempos por HC: extraer 0,1 s (PyMuPDF) / 8 s (pdfplumber); anonimizar ≈ 21–27 s (+ ≈ 37 s la primera
  vez, carga de spaCy); filtrar ≈ 5 s con segmentación; evaluar = 53 consultas (~8.800 tokens c/u).
- Commits: `primerAvance` → `Integración de modulo adaptador LLM y finalizar pipeline` →
  `modulo adaptador LLM y finalizar pipeline` (sincronizado con `origin/main`).

### Pendientes (en orden de prioridad sugerido)

**P1 — Riesgo en resultados (hacer primero)**
- [ ] Con `guardar_evaluacion` comentada se perdió la protección de `todos_fallaron` (esa etapa marcaba
      el documento con error para reanudarlo). Ahora, si caen todos los proveedores, esos ítems llegan
      sin respuesta a `calcular_indicador` y cuentan como **NO sin avisar**. Mover la verificación a
      `evaluar_llm` o `calcular_indicador` (preguntar al usuario).
- [ ] Decidir qué se guarda por HC (hoy solo reporte consolidado, bitácora y `DocumentoTarea.indicador`;
      se pierden `respuesta_cruda`, `valida`, tokens). Posible opción por tarea (`guardar_intermedios`).

**P2 — Frontend (siguiente gran bloque, `../frontend`)**
- [x] Sistema inicial: React 18 + TypeScript + Vite (versiones del lock de gpc-dengue). Pantalla con
      estado de la API (consulta `GET /v1/tareas/en-ejecucion` y `GET /v1/llm/modelos` cada 5 s).
      Cliente en `src/api.ts`. La API no tiene `/health`: no agregar uno sin preguntar.
- [ ] CORS en `main.py` (no hace falta en desarrollo por el proxy de Vite; sí para servir `dist/` aparte).
- [ ] Endpoints de reporte: descargar Excel/JSON de una tarea; regenerar reporte tras cambiar `indicador.yaml`.
- [ ] Posible endpoint de resultados por HC para filtros del front (ámbito de manejo, niveles).
- [ ] `GET /v1/llm/circuitos` (estado de los circuit breakers).

**P3 — Calidad**
- [ ] Sobre-anonimización: spaCy marca rótulos ("Estado civil", "Ocupación", sexo) como
      `<UBICACION>`/`<NOMBRE>` (≈823/520 en una HC). Lista blanca médica / ajustar umbral.
- [ ] Fuga del nombre de la EPS (el patrón toma "EPS SAS" pero no el nombre previo) → diccionario de EPS.
- [ ] Guardar `entidades_anonimizadas` en `DocumentoTarea`.
- [ ] Filtrado: probar modelo multilingüe; ajustar `umbral`; evaluar orden por documento.
- [ ] Validar el indicador contra la evaluación manual de auditores (Excel con códigos 0/1/2).

**P4 — Robustez y rendimiento**
- [ ] Checkpoint por etapa (hoy reanudar repite anonimización y las 53 consultas).
- [ ] Detener no corta dentro de `evaluar_llm` (podría verificarse entre ítems).
- [ ] Paralelismo entre tareas: semáforo por tarea + límite global, configurable.
- [ ] Costo LLM: ~470 k tokens por HC; las correcciones reenvían el prompt completo.
- [ ] Rendimiento de la anonimización (cuello de botella).

**P5 — Infraestructura**
- [ ] Mover `es_core_news_lg` a `models/` (cargar por ruta desde `anonimizacion.yaml`).
- [ ] Fijar versiones exactas (`requirements.lock`).
- [ ] pytest por etapa y endpoints (hoy solo scripts manuales).
- [ ] Configuración por `.env` con `pydantic-settings` (paralelismo, rutas, CORS) y logging estructurado.
- [ ] Empaquetado: Docker (recomendado; evita Smart App Control) o .exe (requiere firma de código).
