# Servicio RAG académico

Sistema académico integrado con Moodle. Procesa documentos PDF, recupera fragmentos con pgvector
y redacta respuestas fundamentadas con DeepSeek. El asistente institucional está disponible en
**http://127.0.0.1:8000/demo** durante la ejecución local.

DeepSeek interpreta las consultas y redacta las respuestas con `deepseek-flash` (V4.1 Flash).
Gemini se conserva únicamente para embeddings de consulta e ingesta (`gemini-embedding-001`,
768 dimensiones); su clave no se usa para generar texto. Las solicitudes protegidas siguen verificando la
aserción firmada de Moodle; Moodle conserva la autoridad sobre identidad y permisos.

Para arquitectura, requisitos, flujos, pruebas, límites y costos, consulta el
[informe técnico integral](docs/informe-integral-rag-service.md).

## Entorno preparado

PostgreSQL y la API se ejecutan en Docker. Configura `DEEPSEEK_API_KEY` y `GEMINI_API_KEY` en
`.env` del servidor RAG; no compartas esas claves con Moodle ni las pongas en el navegador o en el repositorio.
Para comprobar el estado:

```bash
docker compose ps
curl http://127.0.0.1:8000/health
.venv/bin/rag check-providers
.venv/bin/rag ask '¿Cuál es la nota mínima aprobatoria?'
```

`/health` comprueba PostgreSQL y el esquema, sin generar inferencias. Los puertos del proyecto se
publican únicamente en localhost. La API no requiere un contenedor de modelos local.

## Instalación reproducible

Requisitos: Python 3.12 o superior, Docker Compose y claves de DeepSeek y Gemini.

```bash
cd rag-service
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
# Configura DEEPSEEK_API_KEY y GEMINI_API_KEY en .env antes de preparar el servicio.
docker compose up -d db
rag prepare-demo
# El corpus se genera en data/inbox y se indexa con claves estables.
docker compose up --build -d api
```

`prepare-demo` valida DeepSeek y Gemini, aplica las migraciones 001–004, genera once documentos PDF
e ingesta su contenido. Es repetible: documentos idénticos devuelven `unchanged` y no
incrementan versiones. No sobrescribe un PDF existente con contenido diferente. También prepara
embeddings Gemini para los fragmentos ya almacenados; no elimina los espacios antiguos.

Si ya existe `.env`, conservarlo y ajustar sus variables en lugar de copiar el ejemplo encima.
Para preparar componentes individualmente:

```bash
rag prepare-deepseek
rag init-db
rag prepare-gemini-index
rag index-status
```

La ruta conversacional usa DeepSeek Chat Completions con el modelo `deepseek-flash`. La salida JSON
se valida con los modelos Pydantic del RAG; DeepSeek se ejecuta en modo sin razonamiento para
reducir latencia y tokens en estas respuestas estructuradas. Los embeddings de consulta e ingesta
usan `gemini-embedding-001` (768 dimensiones) con tipos de tarea de recuperación.

## Preguntas por página, API y CLI

Abrir `/demo`, escribir una pregunta y consultar. La página muestra espera, errores, respuesta y
fuentes con título, archivo, páginas, versión y texto utilizado. Cada consulta es independiente,
sin historial persistente. Las fuentes cubren matrícula, reglamento, trámites, calendario académico,
biblioteca, bienestar, servicios digitales, becas, integridad académica, accesibilidad e investigación.

```bash
rag ask '¿Cuánto cuesta un certificado de estudios y cuánto tarda su entrega?'
curl http://127.0.0.1:8000/api/v1/chat/query \
  -H 'Authorization: Bearer <aserción firmada de Moodle de corta duración>' \
  -H 'Content-Type: application/json' \
  -d '{"query":"¿Cuál es la nota mínima aprobatoria?"}'
```

`POST /api/v1/chat/query` requiere una aserción Moodle firmada con el secreto compartido
`MOODLE_SERVICE_SECRET`; el RAG falla de forma cerrada si no se configura. Moodle conserva el mismo
secreto en la configuración servidor de `config.php` y nunca lo envía al navegador del chat. Consulta
el [contrato del plugin](../moodle/public/local/acadassistant/README.md). Las rutas sin autenticación
`/api/v1/demo/chat/query` y `/demo` solo existen cuando `LOCAL_DEMO_QUERY_ENABLED=true`. Compose
local activa esa opción y publica el puerto en `127.0.0.1`; desactívala en cualquier entorno
compartido o desplegado.

La aserción autenticada establece identidad y cursos autorizados. El RAG filtra documentos de curso
en PostgreSQL antes de recuperar fragmentos; los documentos institucionales comunes siguen
disponibles para cualquier cuenta Moodle autenticada. El campo `academic_context` queda autenticado
por el hash del cuerpo y se usa únicamente para responder consultas académicas autorizadas.

El flujo conversacional de Moodle usa primero `POST /api/v1/chat/interpret`, con
la misma aserción firmada y vinculada al cuerpo. Recibe `query`, `conversation_context`,
`state` y `runtime` (fecha y zona horaria calculadas por Moodle), y devuelve un plan
cerrado de operaciones permitidas. Moodle vuelve a validar y autorizar esas operaciones;
la interpretación no concede acceso. El segundo envío a `/api/v1/chat/query` añade
`conversation_plan` y `runtime` al contexto académico autorizado. Los clientes existentes
pueden continuar usando el contrato anterior sin esos campos.

El endpoint acepta `query`, no vacía, de hasta 1000 caracteres. Devuelve `answer`, `sources`,
`insufficient_context` y `request_id`. Las fuentes contienen `source_id`, `fragment_id`, `document_id`,
`key`, `title`, `filename`, `version`, `page_start`, `page_end` y `excerpt`.
Si falta información, devuelve HTTP 200 con una explicación y sin fuentes. OpenAPI está en `/docs`.

La consulta se vectoriza con Gemini. Se seleccionan cuatro fragmentos por distancia coseno. Solo se
usan vectores del mismo proveedor, modelo, revisión y dimensión; el espacio debe cubrir el corpus
vigente completo. DeepSeek recibe los fragmentos como datos y devuelve JSON validado. Las referencias
se comprueban contra esos fragmentos, y los metadatos provienen de PostgreSQL. Una referencia válida
no demuestra por sí sola que cada afirmación sea correcta: la evaluación incluye revisión de respuestas.

| Situación | Resultado |
|---|---|
| Pregunta inválida | HTTP 422 |
| Índice incompleto o proveedor/base no disponibles | HTTP 503 |
| Respuesta o embedding inválidos | HTTP 502 |
| Timeout de DeepSeek o Gemini | HTTP 504 |
| Documento cambiado o eliminado durante generación | HTTP 409; repetir consulta |

No se descargan modelos al responder. Las operaciones registran UTC, estado, duración e identificador;
no registran preguntas, texto documental, vectores ni credenciales.

## Administración de PDF

```bash
# En la raíz Moodle (directorio `public/` en este checkout), exportar los cursos existentes:
cd /path/to/moodle/public
php local/acadassistant/cli/export_course_catalog.php > /secure/course-catalog.json
# Transferir el JSON de forma segura al host RAG y reemplazar el catálogo activo:
rag sync-courses /secure/course-catalog.json

# Todos los documentos requieren alcance explícito:
rag ingest data/inbox/reglamento.pdf --key reglamento --title 'Reglamento académico' --kind REGLAMENTO --scope institutional
# Un documento puede asociarse a varios cursos válidos del catálogo (repetir --course-id):
rag ingest data/inbox/silabo.pdf --key silabo-123 --kind SILABO --scope course --course-id 123
rag list
rag ingest data/inbox/reglamento.pdf --key reglamento --kind REGLAMENTO --scope institutional --force
rag delete reglamento
rag index-status
```

El exportador consulta Moodle como fuente confiable de existencia de cursos. `sync-courses` reemplaza
el conjunto activo: si se omite un curso, los documentos asociados dejan de recuperarse hasta que
el curso vuelva a sincronizarse. La ingesta rechaza cursos ausentes del catálogo. Un documento sin
alcance explícito se rechaza; los documentos anteriores a la migración 003 conservan sus vectores,
pero quedan fuera de las respuestas hasta reingerirse con una clasificación revisada. El archivo del
catálogo puede contener identificadores internos y debe transferirse y almacenarse con acceso
restringido.

Los tipos son `REGLAMENTO`, `PROCEDIMIENTO`, `SILABO`, `GUIA` y `OTRO`. La clave identifica el documento
entre versiones; se recomienda especificarla. La extracción conserva página y posición y usa hasta
2000 caracteres por fragmento con solapamiento de 200. PDF de hasta 20 MiB, 300 páginas y 1000 fragmentos.
No hay OCR: se reportan páginas sin texto y se rechazan documentos sin texto extraíble.

La ingesta guarda todos los vectores en una sola transacción, después de calcularlos y validarlos.
Errores conservan la versión anterior. Actualizar o eliminar borra los fragmentos y sus embeddings
obsoletos en cascada; el PDF original permanece. Un bloqueo de sesión serializa operaciones por clave.
`prepare-gemini-index` reconstruye embeddings faltantes desde los textos guardados, sin cambiar versiones.
En una base existente, ejecuta primero `rag init-db` y luego `rag prepare-gemini-index`; hasta
completar ese nuevo espacio el asistente informa índice incompleto. No hay fallback a los vectores
locales o Bedrock antiguos.

## Configuración

El entorno tiene prioridad sobre `.env`. El archivo local, `.venv`, la caché del navegador y los PDF
generados están excluidos de Git. Los contenidos locales y las preguntas de evaluación sí se versionan.

| Variable | Valor inicial |
|---|---|
| `DATABASE_URL` | PostgreSQL local en `localhost:55432` |
| `DEEPSEEK_API_KEY` | Obligatoria para interpretación y respuestas; solo en `.env` del servidor |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` |
| `DEEPSEEK_CHAT_MODEL` | `deepseek-flash` (DeepSeek V4.1 Flash) |
| `DEEPSEEK_TIMEOUT` / `DEEPSEEK_MAX_RETRIES` | 120 segundos / 2 reintentos adicionales (0–3) |
| `GEMINI_API_KEY` | Obligatoria solo para embeddings; guardar en `.env` del servidor |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` |
| `GEMINI_EMBEDDING_DIMENSIONS` | 768 |
| `CHUNK_SIZE_CHARS` / `CHUNK_OVERLAP_CHARS` | 2000 / 200 |

DeepSeek reintenta errores HTTP 408, 429 y 5xx, además de errores de conexión y timeout, con
espera exponencial acotada. Las credenciales y peticiones inválidas no se reintentan. Los errores
de Gemini aplican únicamente al cálculo de embeddings. Cambiar el modelo conversacional no requiere
reconstruir el índice vectorial.

Para repetir la validación real con datos sintéticos y un reloj fijo de Lima:

```bash
.venv/bin/python scripts/check_deepseek_conversation.py --model deepseek-flash \
  --timeout 15 --retries 2 \
  --report ../.scratch/asistente-conversacional/deepseek-live-validation.json
```

El comando realiza llamadas reales y se detiene cuando
el proveedor sigue indisponible tras los reintentos. El informe distingue casos aprobados,
fallidos y no ejecutados mediante `complete`, `cases` y `pending_cases`.

## Pruebas y evaluación

```bash
# Descargar el navegador para las pruebas de la página.
export PLAYWRIGHT_BROWSERS_PATH=.cache/ms-playwright
python -m playwright install chromium
export TEST_DATABASE_URL='postgresql://rag:rag_local_dev@localhost:55432/rag'
pytest -q --strict-markers --require-complete
ruff check .
python scripts/smoke_demo_browser.py
python scripts/evaluate_demo.py
```

La suite usa proveedores simulados y esquemas PostgreSQL temporales; no consume inferencias reales.
Nunca apuntar `TEST_DATABASE_URL` a producción. CI instala Chromium y ejecuta
la suite estricta. Sin navegador o base de pruebas, la aceptación no se considera completa.

La evaluación adicional llama a DeepSeek real a través de la API desplegada. Incluye 36 preguntas
respondibles y 5 sin información. Requiere al menos 80 % de respuestas positivas correctas y
abstención en todas las negativas. Comprueba hechos y fuentes esperados; los resultados completos permiten revisión semántica.
No modifica preguntas ni documentos para acomodar una respuesta fallida. Guarda el informe en
`docs/evaluation-deepseek-results.json`, con respuestas y latencias. El corpus evaluado no certifica
la calidad de todo el sistema ni el objetivo general de diez segundos del PDF.

La validación actual está en [el informe DeepSeek](../docs/validacion-deepseek.md).

Consultar [la trazabilidad del Sprint 1](docs/sprint-1.md) y [la evidencia de validación](docs/validation.md).

La versión anterior a la migración DeepSeek pasó 127 pruebas automáticas y la evaluación fija:
19/20 respuestas positivas
correctas tras revisión semántica, con 5/5 abstenciones. La mediana fue de 22,9 segundos; el informe
documenta un fallo conocido de nombre de trámite. Estos resultados corresponden a la versión histórica del corpus, anterior a su ampliación.
