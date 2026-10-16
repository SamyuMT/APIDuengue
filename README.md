# API Dengue — Procesamiento de historias clínicas

API en **FastAPI** para procesar lotes de historias clínicas en PDF y preparar su evaluación frente a la
Guía de Práctica Clínica (GPC) de dengue. Cada lote (*tarea*) corre en segundo plano por un pipeline:

```
extraer → limpiar → anonimizar → normalizar → filtrar → guardar → guardar_filtraciones
```

- **Extraer**: texto del PDF con PyMuPDF o pdfplumber (intercambiables, patrón Adapter).
- **Limpiar**: solo espacios y líneas vacías (antes de anonimizar, para no romper la detección).
- **Anonimizar**: Microsoft Presidio + spaCy (`es_core_news_lg`) + patrones propios en YAML.
- **Normalizar**: minúsculas, sin tildes ni símbolos raros; conserva etiquetas (`<NOMBRE>`) y fechas.
- **Filtrar**: similitud semántica (sentence-transformers) contra una lista blanca, agrupado por categoría
  (`evaluacion_general`, `diagnostico`, `manejo_ambulatorio`, `manejo_hospitalario`, `manejo_uci`).

Las tareas guardan **checkpoint** después de cada documento: se pueden consultar en vivo, detener,
reanudar desde donde quedaron y eliminar.

## Estructura

```
app/
├── main.py                 # crea la app FastAPI (prefijo /v1)
├── api/
│   ├── router.py           # junta los routers
│   └── routes/             # un archivo por servicio: documents.py, tareas.py
├── service/                # clases con funciones async (orquestación)
├── logic/                  # lógica del sistema, sin FastAPI
│   ├── document_logic.py
│   ├── tarea_logic.py      # crear tarea, checkpoint, progreso
│   └── pipeline/
│       ├── base.py         # Contexto, Etapa, Pipeline
│       ├── flujo.py        # ÚNICO lugar donde se arma el pipeline
│       ├── preprocesamiento/   # extractores (Adapter) + etapa extraer
│       ├── limpieza/           # limpiar, normalizar
│       ├── anonimizador/       # interfaz, config YAML, adaptador Presidio, etapa
│       ├── filtracion/         # lista blanca, segmentador, embedder, similitud, etapa
│       └── out/                # guardar .txt y _filtrado.json
├── schemas/                # modelos Pydantic (request/response/checkpoint)
└── core/rutas.py           # rutas a config/ y models/
config/
├── anonimizacion.yaml      # entidades, etiquetas y regex de anonimización
└── lista_blanca.yaml       # categorías/subcategorías/términos + umbral del filtrado
models/                     # modelos locales (NO se versionan)
data/tareas/                # checkpoints JSON de las tareas
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
| POST | `/v1/tareas/{id}/reanudar` | Reanuda desde el checkpoint (solo documentos no completados) |
| POST | `/v1/tareas/{id}/detener` | Detiene al terminar la etapa en curso (queda `detenida`) |
| DELETE | `/v1/tareas/{id}` | Elimina el checkpoint (solo si no se está ejecutando) |

Ejemplo de creación de tarea:

```json
POST /v1/tareas
{
  "carpeta_entrada": "D:/ruta/pdfs",
  "carpeta_salida": "D:/ruta/resultados",
  "extractor": "pdfplumber",
  "segmentar": true,
  "modelo_embeddings": "all-MiniLM-L6-v2"
}
```

Salida por documento en `<carpeta_salida>/<tarea_id>/`:
- `<pdf>.txt` — texto anonimizado y normalizado.
- `<pdf>_filtrado.json` — `{categoria: texto relevante}`.

## Configuración editable

- `config/anonimizacion.yaml`: qué entidades se anonimizan, su etiqueta y sus regex.
- `config/lista_blanca.yaml`: términos por categoría y `umbral` de similitud.

Se validan al cargar y se releen en cada tarea (no hace falta reiniciar el servidor).

## Nota (Windows)

Si aparece *"Una directiva de Control de aplicaciones bloqueó este archivo"* al importar spaCy/torch,
es Smart App Control bloqueando una DLL sin firmar. Reinstalar el paquete afectado suele resolverlo:
`pip install --force-reinstall --no-deps <paquete>`.

Estado del desarrollo: ver [progreso-proyecto.md](progreso-proyecto.md).
