# Gestor académico RAG — prototipo del Sprint 1

Sistema independiente de Moodle, ubicado en `rag-service/`. Procesa PDF, recupera fragmentos con
pgvector y responde con fuentes mediante Ollama. La página de prueba está en
**http://127.0.0.1:8000/demo**. Usa un corpus académico ficticio, identificado como demostración.

El modo de trabajo predeterminado es **solo Ollama**, sin llamadas automáticas a AWS:
`qwen3-embedding:0.6b` para embeddings y `qwen2.5:3b` para respuestas. La integración con Moodle,
la autenticación para despliegue y las pruebas generales de rendimiento y seguridad quedan para
los siguientes sprints.

## Entorno preparado

En este equipo ya están instaladas las dependencias y los modelos. PostgreSQL y la API se ejecutan
en Docker. `.env` fija los modelos locales y distingue las direcciones Ollama desde el host y Docker.
Para comprobar el estado:

```bash
docker compose ps
curl http://127.0.0.1:8000/health
.venv/bin/rag check-ollama
.venv/bin/rag ask '¿Cuál es la nota mínima aprobatoria?'
```

`/health` comprueba PostgreSQL y el esquema, sin generar inferencias. Los puertos del proyecto se
publican únicamente en localhost. Los modelos viven en el contenedor Ollama existente; no se
sustituye el contenedor ni se elimina `llama3.2:3b`.

## Instalación reproducible

Requisitos: Python 3.12 o superior, Docker Compose y un servidor Ollama accesible.

```bash
cd rag-service
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
docker compose up -d db
rag prepare-demo
# El corpus se genera en data/inbox y se indexa con claves estables.
docker compose up --build -d api
```

`prepare-demo` comprueba o prepara ambos modelos, aplica las migraciones 001 y 002, genera tres PDF
ficticios e ingesta su contenido. Es repetible: documentos idénticos devuelven `unchanged` y no
incrementan versiones. No sobrescribe un PDF existente con contenido diferente. También prepara
el índice local para los demás documentos ya almacenados; no los elimina.

Si ya existe `.env`, conservarlo y ajustar sus variables en lugar de copiar el ejemplo encima.
Para preparar componentes individualmente:

```bash
rag prepare-ollama
rag prepare-chat
rag init-db
rag prepare-local-index
rag index-status
```

Si no existe un servidor Ollama, se puede añadir `compose.ollama.yaml`. Si ya hay uno, configurar
`OLLAMA_DOCKER_BASE_URL` con su dirección accesible desde el contenedor. `localhost` dentro de
Docker identifica al contenedor, no al host. No levantar un segundo servidor si el puerto 11434
ya está ocupado. Más detalles en [la guía de Ollama](docs/fallback-ollama.md).

## Preguntas por página, API y CLI

Abrir `/demo`, escribir una pregunta y consultar. La página muestra espera, errores, respuesta y
fuentes con título, archivo, páginas, versión y texto utilizado. Cada consulta es independiente,
sin historial persistente. Los documentos describen la **Universidad Demo del Valle**, que es ficticia.

```bash
rag ask '¿Cuánto cuesta un certificado de estudios y cuánto tarda su entrega?'
curl http://127.0.0.1:8000/api/v1/chat/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"¿Cuál es la nota mínima aprobatoria?"}'
```

El endpoint acepta `query`, no vacía, de hasta 1000 caracteres. Devuelve `answer`, `sources`,
`insufficient_context` y `request_id`. Las fuentes contienen `source_id`, `fragment_id`, `document_id`,
`key`, `title`, `filename`, `version`, `page_start`, `page_end` y `excerpt`.
Si falta información, devuelve HTTP 200 con una explicación y sin fuentes. OpenAPI está en `/docs`.

La consulta se vectoriza con el modelo local; para Qwen se añade una instrucción de recuperación
solo a la pregunta, siguiendo su formato recomendado. Se seleccionan cuatro fragmentos por distancia
coseno. Solo se usan vectores del mismo modelo, digest y dimensión; el espacio debe cubrir el corpus
vigente completo. Ollama recibe los fragmentos como datos y devuelve JSON validado. Las referencias
se comprueban contra esos fragmentos, y los metadatos provienen de PostgreSQL. Una referencia válida
no demuestra por sí sola que cada afirmación sea correcta: la evaluación incluye revisión de respuestas.

| Situación | Resultado |
|---|---|
| Pregunta inválida | HTTP 422 |
| Índice incompleto o proveedor/base no disponibles | HTTP 503 |
| Respuesta o embedding inválidos | HTTP 502 |
| Timeout de Ollama | HTTP 504 |
| Documento cambiado o eliminado durante generación | HTTP 409; repetir consulta |

No se descargan modelos al responder. Las operaciones registran UTC, estado, duración e identificador;
no registran preguntas, texto documental, vectores ni credenciales.

## Administración de PDF

```bash
rag ingest data/inbox/reglamento.pdf --key reglamento --title 'Reglamento académico' --kind REGLAMENTO
rag list
rag ingest data/inbox/reglamento.pdf --key reglamento --kind REGLAMENTO --force
rag delete reglamento
rag index-status
```

Los tipos son `REGLAMENTO`, `PROCEDIMIENTO`, `SILABO`, `GUIA` y `OTRO`. La clave identifica el documento
entre versiones; se recomienda especificarla. La extracción conserva página y posición y usa hasta
2000 caracteres por fragmento con solapamiento de 200. PDF de hasta 20 MiB, 300 páginas y 1000 fragmentos.
No hay OCR: se reportan páginas sin texto y se rechazan documentos sin texto extraíble.

La ingesta guarda todos los vectores en una sola transacción, después de calcularlos y validarlos.
Errores conservan la versión anterior. Actualizar o eliminar borra los fragmentos y sus embeddings
obsoletos en cascada; el PDF original permanece. Un bloqueo de sesión serializa operaciones por clave.
`prepare-local-index` reconstruye las copias faltantes desde los textos guardados, sin cambiar versiones.

## Configuración

El entorno tiene prioridad sobre `.env`. El archivo local, `.venv`, la caché del navegador y los PDF
generados están excluidos de Git. Los contenidos ficticios y las preguntas de evaluación sí se versionan.

| Variable | Valor inicial |
|---|---|
| `DATABASE_URL` | PostgreSQL local en `localhost:55432` |
| `EMBEDDING_BACKEND` | `ollama` |
| `OLLAMA_BASE_URL` | `http://localhost:11434`, CLI en el host |
| `OLLAMA_DOCKER_BASE_URL` | `http://host.docker.internal:11434`, usado por Compose |
| `OLLAMA_EMBEDDING_MODEL` | `qwen3-embedding:0.6b` |
| `OLLAMA_EMBEDDING_CONTEXT_LENGTH` | 2048 tokens; entradas mayores se rechazan sin truncar |
| `OLLAMA_CHAT_MODEL` | `qwen2.5:3b` |
| `OLLAMA_CHAT_NUM_GPU` | -1: selección automática; 0 fuerza CPU |
| `OLLAMA_TIMEOUT` / `OLLAMA_CHAT_TIMEOUT` | 120 segundos por operación HTTP |
| `OLLAMA_PULL_TIMEOUT` | 1800 segundos para preparación |
| `CHUNK_SIZE_CHARS` / `CHUNK_OVERLAP_CHARS` | 2000 / 200 |

Bedrock se conserva como integración futura, desactivada en la configuración de trabajo. No es
necesario montar credenciales AWS para utilizar este prototipo. Su guía y los resultados históricos
de cuota están en la documentación; este cierre no certifica que Bedrock funcione.

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

La suite usa proveedores simulados y esquemas PostgreSQL temporales; no llama a AWS ni consume
inferencias reales. Nunca apuntar `TEST_DATABASE_URL` a producción. CI instala Chromium y ejecuta
la suite estricta. Sin navegador o base de pruebas, la aceptación no se considera completa.

La evaluación adicional sí llama al Ollama real a través de la API desplegada. Tiene 20 preguntas
respondibles y 5 sin información. Requiere al menos 16 respuestas correctas y abstención en las cinco
negativas. Comprueba hechos y fuentes esperados; los resultados completos permiten revisión semántica.
No modifica preguntas ni documentos para acomodar una respuesta fallida. Guarda el informe en
`docs/evaluation-results.json`, con respuestas y latencias. El corpus pequeño y ficticio no certifica
la calidad de todo el sistema ni el objetivo general de diez segundos del PDF.

Consultar [la trazabilidad del Sprint 1](docs/sprint-1.md) y [la evidencia de validación](docs/validation.md).

La entrega local pasó 127 pruebas automáticas y la evaluación fija: 19/20 respuestas positivas
correctas tras revisión semántica, con 5/5 abstenciones. La mediana fue de 22,9 segundos; el informe
documenta un fallo conocido de nombre de trámite. Estos resultados corresponden al corpus ficticio.
