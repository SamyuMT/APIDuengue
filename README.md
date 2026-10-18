# API Dengue — Adherencia de historias clínicas a la GPC

API en **FastAPI** que procesa lotes de historias clínicas (HC) en PDF y calcula su adherencia a la
Guía de Práctica Clínica (GPC) de dengue. Cada lote (*tarea*) corre en segundo plano por un pipeline:

```
extraer → limpiar → anonimizar → normalizar → filtrar → evaluar_llm → calcular_indicador
                                                          ↓ al terminar la tarea
                                              reporte_adherencia.xlsx / .json
```

- **Extraer**: texto del PDF con PyMuPDF o pdfplumber (intercambiables, patrón Adapter).
- **Limpiar**: solo espacios y líneas vacías (antes de anonimizar, para no romper la detección).
- **Anonimizar**: Microsoft Presidio + spaCy (`es_core_news_lg`) + patrones propios en YAML.
- **Normalizar**: minúsculas, sin tildes ni símbolos raros; conserva etiquetas (`<NOMBRE>`) y fechas.
- **Filtrar**: similitud semántica (sentence-transformers) contra una lista blanca, agrupado por categoría
  (`evaluacion_general`, `diagnostico`, `manejo_ambulatorio`, `manejo_hospitalario`, `manejo_uci`).
- **Evaluar con LLM**: un prompt por ítem de la GPC con el texto filtrado de su grupo. Usa el modelo
  principal de la tarea y, si falla, los demás modelos vinculados (reintentos + circuit breaker). La
  respuesta se valida: solo SI / NO / PARCIAL; si no, se pide corrección (hasta 2 veces) y luego NO.
- **Calcular indicador**: puntaje por ítem, promedio por módulo, indicadores macro (evaluación general,
  diagnóstico, manejo), calificación total y nivel (BAJO / MEDIO / ALTO).

Además hay un **servicio LLM independiente** para vincular modelos, hacer consultas y mantener chats.

Las tareas guardan **checkpoint** después de cada documento: se pueden consultar en vivo, detener,
reanudar desde donde quedaron y eliminar.

## Estructura

```
app/
├── main.py                 # crea la app FastAPI (prefijo /v1) y carga el .env
├── api/
│   ├── router.py           # junta los routers
│   └── routes/             # un archivo por servicio: documents.py, tareas.py, llm.py
├── service/                # clases con funciones async (orquestación)
├── logic/                  # lógica del sistema, sin FastAPI
│   ├── document_logic.py
│   ├── tarea_logic.py      # crear tarea, checkpoint, progreso, reporte final
│   ├── llm/                # núcleo LLM: registro de modelos, clientes (Adapter), chats
│   └── pipeline/
│       ├── base.py         # Contexto, Etapa, Pipeline
│       ├── flujo.py        # ÚNICO lugar donde se arma el pipeline
│       ├── preprocesamiento/   # extractores (Adapter) + etapa extraer
│       ├── limpieza/           # limpiar, normalizar
│       ├── anonimizador/       # interfaz, config YAML, adaptador Presidio, etapa
│       ├── filtracion/         # lista blanca, segmentador, embedder, similitud, etapa
│       ├── llm/                # enrutador, circuit breaker, validador, bitácora, etapa evaluar
│       ├── indicador/          # cálculo del indicador, etapa y reporte consolidado
│       └── out/                # etapas de guardado por HC (opcionales, ver abajo)
├── schemas/                # modelos Pydantic (request/response/checkpoint)
└── core/rutas.py           # rutas a config/, models/ y data/
config/                     # configuración editable (YAML)
models/                     # modelos locales (NO se versionan)
data/
├── tareas/                 # checkpoints JSON de las tareas
└── llm/                    # modelos LLM vinculados (y chats, fuera de git)
tests/                      # PDFs de prueba y resultados
```

## Instalación

Requiere **Python 3.13**.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt  # incluye el modelo spaCy es_core_news_lg (~570 MB)
copy .env.example .env           # completar las llaves
```

### Modelos (carpeta `models/`)

La herramienta **no descarga nada al ejecutar**: los modelos deben estar en `models/`.

```bash
# Modelo de embeddings para el filtrado
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2').save('models/all-MiniLM-L6-v2')"

# Segmentador de oraciones de NLTK
python -c "import nltk; nltk.download('punkt_tab', download_dir='models/nltk_data')"
```

Para usar otro modelo de embeddings basta con guardarlo en `models/<nombre>` y enviar ese nombre al crear
la tarea (`modelo_embeddings`).

## Ejecutar

```bash
python -m uvicorn app.main:app --reload
```

Documentación interactiva: http://127.0.0.1:8000/docs

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/v1/documents/list` | Lista los PDF de una carpeta y el total |
| POST | `/v1/tareas` | Crea y lanza una tarea; devuelve `tarea_id` (202) |
| GET | `/v1/tareas/{id}` | Estado, progreso, etapas y etapa actual de cada documento |
| GET | `/v1/tareas/pendientes` | Tareas no completadas que se pueden reanudar |
| GET | `/v1/tareas/en-ejecucion` | Tareas corriendo ahora: progreso, etapa de cada documento en curso y si se están deteniendo |
| POST | `/v1/tareas/{id}/reanudar` | Reanuda desde el checkpoint (solo documentos no completados) |
| POST | `/v1/tareas/{id}/detener` | Detiene al terminar la etapa en curso (queda `detenida`) |
| DELETE | `/v1/tareas/{id}` | Elimina el checkpoint (solo si no se está ejecutando) |
| GET | `/v1/llm/modelos` | Modelos LLM vinculados (sin llaves; indica si la llave está configurada) |
| POST | `/v1/llm/modelos` | Vincula o reemplaza un modelo; si trae `api_key` se guarda en el `.env` |
| DELETE | `/v1/llm/modelos/{nombre}` | Desvincula un modelo |
| POST | `/v1/llm/consulta` | Pregunta y respuesta (`modelo`, `prompt`, `system`, `formato_json`...) |
| POST | `/v1/llm/chats` | Crea un chat con un modelo; devuelve `chat_id` |
| POST | `/v1/llm/chats/{id}/mensajes` | Envía un mensaje; el modelo recibe todo el historial |
| GET | `/v1/llm/chats/{id}` | Historial del chat |

### Uso típico

1. Vincular al menos un modelo LLM (cualquier proveedor compatible con la API de OpenAI, cambiando
   `base_url`: OpenAI, DeepSeek, Gemini, Anthropic, LM Studio, Ollama...):

```json
POST /v1/llm/modelos
{ "nombre": "deepseek", "modelo": "deepseek-chat", "base_url": "https://api.deepseek.com",
  "api_key_env": "DEEPSEEK_API_KEY", "api_key": "sk-..." }
```

2. Crear la tarea con el modelo principal (si falla, se usan los demás vinculados):

```json
POST /v1/tareas
{
  "carpeta_entrada": "D:/ruta/pdfs",
  "carpeta_salida": "D:/ruta/resultados",
  "extractor": "pdfplumber",
  "segmentar": true,
  "modelo_embeddings": "all-MiniLM-L6-v2",
  "modelo_llm": "deepseek"
}
```

3. Consultar el avance con `GET /v1/tareas/{id}` o `GET /v1/tareas/en-ejecucion`.

### Salidas en `<carpeta_salida>/<tarea_id>/`

Siempre:
- `reporte_adherencia.xlsx` — hoja *Por HC* (una fila por HC: códigos 0/1/2 por ítem, calificación por
  módulo, manejo, total y niveles) y hoja *General* (promedio y nivel de cada indicador).
- `reporte_adherencia.json` — indicadores generales (`general`, `niveles_general`) y por HC (`por_hc`).
- `llm_intentos.jsonl` — bitácora de cada intento contra los modelos LLM (sin prompt ni texto clínico).

Opcionales por HC (etapas `guardar_*` de `pipeline/out/`, hoy desactivadas en `flujo.py`):
- `<pdf>.txt` (texto anonimizado), `<pdf>_filtrado.json`, `<pdf>_evaluacion.json`, `<pdf>_indicador.json`.

## Indicador de adherencia

| Respuesta | Código (Excel) | Puntaje |
|---|---|---|
| NO | 0 | 1 |
| SI | 1 | 5 |
| PARCIAL | 2 | 5 (configurable) |

- Módulo = promedio de sus ítems. Manejo = promedio de ambulatorio, hospitalario y UCI.
- Total = promedio de evaluación general, diagnóstico y manejo.
- Ítems 14, 24 y 25 no califican; si el ítem 14 es NO, los ítems 17 y 18 no tienen valor.
- Nivel: BAJO < 3, MEDIO de 3 a < 4, ALTO ≥ 4.

## Configuración editable

- `config/anonimizacion.yaml`: qué entidades se anonimizan, su etiqueta y sus regex.
- `config/lista_blanca.yaml`: términos por categoría y `umbral` de similitud.
- `config/evaluacion_llm.yaml`: archivo de prompts, temperatura, `max_tokens`, reintentos, circuit breaker
  y validación de respuestas.
- `config/prompts/gpc_v1.yaml`, `gpc_v2.yaml`: prompts por ítem de la GPC.
- `config/indicador.yaml`: códigos, puntajes, módulos, niveles, ítems excluidos y reglas condicionales.

Se validan al cargar y se releen en cada tarea (no hace falta reiniciar el servidor).
En YAML, escribir `"NO"` entre comillas (sin comillas es el booleano `false`).

## Estado

- Pipeline completo funcionando, probado de punta a punta con DeepSeek (2 HC, reporte generado).
- Pendientes principales: calidad de la anonimización (sobre-anonimización, fuga del nombre de la EPS),
  modelo de embeddings multilingüe, validar el indicador contra auditores, protección cuando fallan todos
  los modelos LLM (hoy esos ítems cuentan como NO), endpoints para regenerar/descargar el reporte,
  pruebas automáticas y empaquetado (Docker).

Detalle completo de lo hecho y lo pendiente: [CLAUDE.md](CLAUDE.md).

## Nota (Windows)

Si aparece *"Una directiva de Control de aplicaciones bloqueó este archivo"* al importar spaCy/torch,
es Smart App Control bloqueando una DLL sin firmar. Reinstalar el paquete afectado suele resolverlo:
`pip install --force-reinstall --no-deps <paquete>`.
