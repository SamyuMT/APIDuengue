# Progreso del proyecto

Última actualización: 2026-10-16 · Avance 1

## Hecho

### 1. Base de la API
- Estructura limpia por capas: `routes` (HTTP) → `service` (clases async) → `logic` (lógica pura) + `schemas`.
- Servicio **documents**: `POST /v1/documents/list` devuelve los PDF de una carpeta y el total.

### 2. Servicio de tareas (núcleo de ejecución por lotes)
- Crear tarea → responde de inmediato con `tarea_id`; el lote corre en segundo plano (`asyncio.Task`).
- El pipeline (síncrono) corre en hilos (`asyncio.to_thread`), máximo 2 documentos en paralelo.
- **Checkpoint** JSON por tarea (`data/tareas/<id>.json`), escritura atómica, guardado después de cada documento.
- **Progreso en vivo**: total, procesados, porcentaje y etapa actual de cada documento.
- **Reanudar** desde el checkpoint (solo documentos no completados). Si el servidor se cae, la tarea aparece
  como `interrumpida`.
- **Detener** (cooperativo, entre etapas) → estado `detenida`, reanudable.
- **Eliminar** checkpoint solo si la tarea no se está ejecutando. Los resultados se conservan.
- Los parámetros de la tarea (`extractor`, `segmentar`, `modelo_embeddings`) quedan en el checkpoint, así
  se reanuda con la misma configuración.

### 3. Pipeline
| Etapa | Implementación | Notas |
|---|---|---|
| extraer | Adapter `ExtractorPdf` → PyMuPDF / pdfplumber | Se elige con `extractor` |
| limpiar | Espacios y líneas vacías | Antes de anonimizar |
| anonimizar | Adapter `Anonimizador` → Presidio + spaCy `es_core_news_lg` | Config en `config/anonimizacion.yaml` |
| normalizar | Minúsculas, sin tildes ni símbolos | Conserva etiquetas, fechas, `/`, `%`, `°` |
| filtrar | sentence-transformers + lista blanca | Con o sin segmentación (NLTK) |
| guardar / guardar_filtraciones | `.txt` y `_filtrado.json` | |

- **Anonimización**: patrones del notebook de pruebas pasados a YAML (validados con Pydantic al cargar),
  ajustados para no cruzar líneas y exigir dígitos en identificadores. Las detecciones de spaCy que cruzan
  saltos de línea se parten por línea. El texto original no sigue en el pipeline.
- **Filtrado**: lista blanca en YAML (generada desde el notebook), modelo cargado desde `models/<nombre>`
  sin internet. **Verificado: reproduce exactamente los 4 JSON del notebook** (Mu/Plu × con/sin segmentación).

### 4. Pruebas realizadas
- API: creación, consulta, reanudación tras error, detener y eliminar.
- Lote real (45 copias de una HC de prueba, pdfplumber, 18 procesadas):
  extraer ≈ 8 s (pdfplumber) / 0,1 s (PyMuPDF), anonimizar ≈ 27 s, filtrar ≈ 5 s por documento.
- Verificación de fugas: documento, teléfono, dirección, fecha de nacimiento e identificador único quedan
  anonimizados.

## Pendiente

### Calidad de la anonimización
- [ ] **Sobre-anonimización**: spaCy etiqueta como `<UBICACION>`/`<NOMBRE>` rótulos y términos
      ("Estado civil", "Ocupación", sexo). Revisar si se pierden términos clínicos.
- [ ] **Fuga del nombre de la EPS**: el patrón toma "EPS SAS" pero no el nombre previo. Usar diccionario de EPS.
- [ ] Diccionarios (nombres, EPS, instituciones) y lista blanca médica para no anonimizar términos clínicos.
- [ ] Guardar `entidades_anonimizadas` (conteo por tipo) en el checkpoint para trazabilidad.

### Filtrado
- [ ] Probar un modelo multilingüe (p. ej. `paraphrase-multilingual-MiniLM-L12-v2`); `all-MiniLM-L6-v2` es solo inglés.
- [ ] Evaluar ordenar las oraciones por orden del documento en lugar de por score.
- [ ] Ajustar el `umbral` con datos reales.

### Siguientes etapas del pipeline
- [ ] Consulta al LLM por ítem de la GPC (con resiliencia: reintentos / circuit breaker).
- [ ] Validación de la respuesta del LLM.
- [ ] Puntuación de adherencia y reporte consolidado (Excel/CSV).

### Infraestructura
- [ ] Mover `es_core_news_lg` a `models/` para que todos los modelos estén en un solo lugar.
- [ ] Fijar versiones exactas de dependencias (`requirements.lock`).
- [ ] Empaquetado: Docker (recomendado) o .exe (requiere firma de código por Smart App Control).
- [ ] Pruebas automáticas (pytest) por etapa y de los endpoints.
- [ ] Logging estructurado y configuración por `.env` (`pydantic-settings`).
- [ ] Rendimiento: la anonimización es el cuello de botella (~27 s/doc).
