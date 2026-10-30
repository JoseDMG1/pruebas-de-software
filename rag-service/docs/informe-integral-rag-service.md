# Informe técnico integral del sistema `rag-service`

**Fecha de corte:** 22 de octubre de 2026 (America/Lima)  
**Sistema revisado:** árbol de trabajo local de `rag-service` integrado con el plugin Moodle del mismo espacio de trabajo.  
**Estado del documento:** inventario técnico y evaluación de preparación; no es certificación de seguridad, auditoría independiente ni autorización de producción.

## 1. Resumen ejecutivo

`rag-service` es una API Python/FastAPI para recuperación documental universitaria y coordinación acotada de un asistente conversacional conectado a Moodle. Al momento del corte, la configuración local activa DeepSeek `deepseek-flash` (DeepSeek V4.1 Flash) para interpretar consultas y seleccionar evidencia, Gemini `gemini-embedding-001` de 768 dimensiones para vectores, y PostgreSQL con pgvector para documentos, fragmentos y espacios de embeddings. Moodle conserva el registro académico y decide quién puede consultar o abrir cada recurso; el RAG no se conecta directamente a la base de datos de Moodle.

El diseño es **un agente conversacional con varias etapas**, no un conjunto de agentes que se delegan trabajo. DeepSeek propone una clasificación y planes JSON; el RAG valida esa salida; Moodle vuelve a validar el plan, consulta sus APIs/datos con permisos efectivos y construye los enlaces. Los hechos académicos se formatean a partir de los datos recibidos de Moodle. La ruta documental genera embeddings, recupera hasta cuatro fragmentos autorizados y usa DeepSeek para escoger pasajes literales verificables.

La evaluación documental guardada está marcada completa: 41 consultas secuenciales, 35/36 positivas con acierto automático, 5/5 abstenciones, fuente esperada en 36/36 positivas, p50 2,629 s y p95 3,016 s. La revisión guardada juzga P19 como falso negativo del comparador literal y no reporta errores factuales en las 36 respuestas revisadas; esa revisión no fue independiente. El recorrido completo anterior en Moodle reporta 72 consultas completas, p50 3,49 s y p95 8,13 s. Ninguna de estas medidas es prueba de carga.

En la última suite local registrada para el árbol actual, pasaron 260 pruebas y 14 pruebas de integración se omitieron porque no estaba definida `TEST_DATABASE_URL`. Por eso `--require-complete` marca esa ejecución como incompleta. La suite PHPUnit independiente de Moodle pasó 53 pruebas y 243 aserciones en la última validación conversacional. Ruff no reportó errores. Estos resultados no acreditan el despliegue actual: en la inspección de este informe, ambos `docker compose ps` estaban vacíos y `http://127.0.0.1:8000/health` no respondía.

**Conclusión de preparación:** buen prototipo integrado para demostración controlada; faltan pruebas de carga, observabilidad de consumo/costos, continuidad operativa, controles de despliegue y gobierno de datos antes de presentarlo como servicio institucional de producción.

## 2. Alcance, límites y arquitectura

### 2.1 Componentes

| Componente | Responsabilidad | Tecnología/estado configurado |
|---|---|---|
| Plugin Moodle | Identidad, permisos, lecturas de cursos/tareas/notas/calendario, estado conversacional y navegación | Moodle 5.3dev; PHP; PostgreSQL de Moodle, separado de la base RAG |
| API RAG | Interpretación acotada, recuperación documental, composición de respuestas, autenticación entre servicios | Python 3.12 en Docker; FastAPI; Pydantic |
| Persistencia documental | Documentos, versiones, metadatos, cursos sincronizados, fragmentos y vectores | PostgreSQL 17 con pgvector; esquema versionado hasta migración 004 |
| Generación y clasificación | Interpretación JSON y selección de pasajes | DeepSeek Chat Completions, `deepseek-flash`; modo de razonamiento desactivado |
| Embeddings | Vectorizar PDF y consultas documentales | Gemini Developer API `gemini-embedding-001`, 768 dimensiones |
| CLI de administración | Ingesta, sincronización del catálogo, estado, eliminación y preparación | `rag` entry point local |
| Demo web/API | Probar consultas documentales sin el flujo Moodle | `/demo` y `/api/v1/demo/chat/query`, habilitables por configuración; no autentican usuario |

El detalle de módulos y configuración vive en [README.md](../README.md), [api.py](../src/rag_service/api.py), [config.py](../src/rag_service/config.py), [conversation.py](../src/rag_service/conversation.py), [query.py](../src/rag_service/query.py), [moodle_auth.py](../src/rag_service/moodle_auth.py), [repository.py](../src/rag_service/repository.py) y [compose.yaml](../compose.yaml).

### 2.2 Límites de confianza

- Moodle es la autoridad para identidad, matrículas, capacidades, calificaciones y destinos. Envía al RAG un contexto académico ya autorizado y una lista de cursos permitidos.
- El RAG tiene su propia base PostgreSQL/pgvector. Esa base guarda catálogo mínimo de IDs de cursos para clasificar sílabos y documentos; no sustituye la base Moodle.
- El modelo no autoriza operaciones, no recibe credenciales Moodle, no construye URLs de Moodle ni ejecuta SQL, comandos o escrituras académicas.
- DeepSeek y Gemini son proveedores externos. Consultas, historial pertinente y/o contenido documental enviado a sus APIs salen del host local; se debe gobernar ese tratamiento antes de usar datos personales o documentos restringidos de una institución real.
- Los datos y documentos usados para la presentación son fixtures/corpus de demostración. La instalación no está conectada a una base universitaria productiva.

## 3. Requerimientos funcionales

Las siguientes claves son una línea base para control y aceptación; los archivos enlazados son la evidencia de implementación. “Parcial” significa que la función existe con límites explícitos o que su aceptación de extremo a extremo no se ha demostrado en este corte.

| ID | Requerimiento | Estado | Criterio/evidencia |
|---|---|---|---|
| FR-01 | Ingerir PDF institucional o asociado a uno o varios cursos activos | Implementado | Clasificación obligatoria `institutional`/`course`; tipo, clave y título; el catálogo debe validarse contra el catálogo sincronizado de Moodle. |
| FR-02 | Extraer texto, página y metadatos y segmentar documentos | Implementado con límites | pypdf; página conservada; fragmentos de 2.000 caracteres con solapamiento de 200; máximo 20 MiB, 300 páginas y 1.000 fragmentos; sin OCR. |
| FR-03 | Crear, identificar y reindexar embeddings sin mezclar espacios | Implementado | Espacio identificado por proveedor, modelo, revisión y dimensión; consulta exige cobertura completa del corpus visible; migración/reindexación versionadas. |
| FR-04 | Recuperar evidencia semántica por similitud | Implementado | Gemini `RETRIEVAL_QUERY`; pgvector ordena por distancia coseno; máximo cuatro fragmentos por búsqueda. |
| FR-05 | Responder preguntas documentales con fuente identificable | Implementado con alcance acotado | DeepSeek elige hasta tres pasajes candidatos; el backend comprueba que cada cita sea un texto literal de la fuente actual y construye título, archivo, versión y páginas. Sin evidencia adecuada, se abstiene. |
| FR-06 | Separar documentos institucionales de documentos de curso | Implementado | El filtro SQL permite documentos institucionales y documentos solo de cursos autorizados y activos; se aplica antes de devolver fragmentos al modelo. |
| FR-07 | Autenticar llamadas Moodle→RAG | Implementado | Bearer JWT firmado HS256, secreto de al menos 32 caracteres, issuer/audience, vencimiento máximo 120 s, tolerancia de reloj 30 s, usuario/cursos validados y hash SHA-256 del cuerpo exacto. |
| FR-08 | Interpretar lenguaje conversacional y seguimientos | Implementado con validación determinista | El modelo produce un plan cerrado JSON; esquemas Pydantic y Moodle validan intents, categorías, ámbitos y límites. Historial del contrato admite hasta cuatro turnos. |
| FR-09 | Consultar categorías académicas | Implementado en el sistema integrado | Cursos (matriculados, accesibles o que enseña), docentes visibles, tareas pendientes/entregadas/todas, calificaciones visibles y calendario. Moodle efectúa las lecturas y aplica capacidades. |
| FR-10 | Preparar un plan semanal personalizado | Implementado con límites | Usa tareas pendientes, fechas efectivas, disponibilidad explícita, semana y prioridades. No estima esfuerzo; informa tareas vencidas/sin fecha y limita el detalle de grupos a seis filas y hasta ocho bloques. |
| FR-11 | Navegar a destinos Moodle autorizados | Implementado en el plugin integrado | El modelo propone el tipo de operación; Moodle verifica permisos y construye enlaces para cursos, tareas, reportes de notas/calificación y calendario. Para vencimiento más próximo devuelve empates de tareas pendientes futuras; no realiza escrituras. |
| FR-12 | Mantener respuestas académicas fieles a datos Moodle | Implementado | El RAG redacta las categorías desde el contexto autorizado; Moodle conserva autoridad y filtros. El modelo no inventa el dato de origen. |
| FR-13 | Administrar corpus y catálogo | Implementado por CLI | `init-db`, `ingest`, `sync-courses`, `list`, `delete`, `prepare-deepseek`, `prepare-gemini`, `prepare-gemini-index`, `index-status`, `ask`, `prepare-demo`. No hay una API administrativa remota de ingesta. |
| FR-14 | Ofrecer respuesta social, aclaración y límites | Implementado | Saludo/cortesía/capacidades con plantillas; preguntas ambiguas piden precisión; alcance no universitario, resolver ejercicios y finanzas personales se bloquean o separan de una petición permitida. |
| FR-15 | Exponer una demo documental independiente | Configurable; habilitada en `.env` local | `/demo` y `/api/v1/demo/chat/query` son rutas sin autenticación si `LOCAL_DEMO_QUERY_ENABLED=true`; Compose liga los puertos a localhost. Deben deshabilitarse o aislarse antes de cualquier exposición compartida. |

### 3.1 Intenciones y servicios conversacionales

El contrato de plan acepta `social`, `capabilities`, `academic`, `document`, `weekly_plan`, `clarify` y `blocked`; navegación se representa como operación académica con los modos `open`, `nearest_deadline` y `grading`. Las categorías admitidas son `courses`, `teachers`, `assignments`, `grades` y `calendar`.

| Flujo | Trabajo que se realiza | Salida/límite |
|---|---|---|
| Saludo, agradecimiento o despedida | DeepSeek clasifica la intención; una segunda clasificación social puede precisarla; el texto final es plantilla | No consulta documentos ni Moodle salvo que el mismo mensaje contenga otra petición permitida |
| “¿Qué puedes hacer?” | Plan `capabilities` validado | Lista breve de capacidades; no hace lecturas |
| Consulta académica | DeepSeek interpreta consulta/alcance; Moodle valida y lee los registros visibles; RAG compone la respuesta | Cursos, docentes, tareas, calificaciones y calendario autorizados; un resultado vacío no se presenta como error documental |
| Consulta documental | Moodle entrega la cláusula documental y cursos que puede consultar; Gemini vectoriza; PostgreSQL filtra y busca; DeepSeek verifica institución y selecciona pasajes literales | Respuesta respaldada por citas/fuentes o abstención. El conjunto recuperado se limita a cuatro fragmentos |
| Petición mixta | Se separa la parte académica de la parte documental y/o no permitida | La parte permitida puede responderse; cada dato conserva su fuente y alcance |
| Navegación | Interpretación devuelve una intención de destino; Moodle revisa visibilidad/capacidades y construye URL nativa | Enlace clicable; no hace clic, entrega tarea, cambia nota, ni modifica configuración |
| Vencimiento próximo | Moodle examina tareas pendientes futuras, prórrogas y paginación; conserva todos los empates | Si la lectura es parcial, solicita acotar; no afirma un mínimo global incompleto |
| Plan semanal | DeepSeek extrae horario/semana/prioridades declarados; Moodle lee tareas reales; RAG aplica reglas temporales deterministas | Propuesta informativa, no estimación de esfuerzo ni garantía de terminar |
| Aclaración/seguimiento | Estado e historial acotado ayudan a resolver “esa”, “continúa”, curso o tarea; planes inválidos se rechazan | No hereda un ámbito ambiguo ni concede acceso por un rol declarado en texto |
| Petición fuera del alcance | Plan bloqueado o parte bloqueada | No consulta pagos personales, no resuelve ejercicios ni sigue instrucciones de secretos/código |

**Cómputo de llamadas de modelo:** un mensaje conversacional protegido llega primero a `/interpret`. Las rutas académicas/documentales suelen ejecutar clasificación y una segunda extracción/validación; saludos, bloqueos y aclaraciones pueden finalizar antes. La ruta de plan extrae disponibilidad; el flujo social y la confirmación docente tienen verificaciones adicionales. Los datos académicos que devuelve Moodle se formatean de manera determinista y no requieren una generación final libre. Una pregunta documental además usa Gemini para un embedding y DeepSeek para selección de institución/pasaje (la selección de institución se realiza incluso cuando se omite institución, según el flujo de evidencia). El número exacto varía por intención y no se guarda tokenización/uso por llamada.

### 3.2 Lo que el servicio no ofrece

- No es un sistema SIS, LMS ni fuente de verdad de calificaciones, matrícula, docentes, pagos o cursos.
- No escribe en Moodle: no entrega tareas, califica, cambia matrículas, crea cursos, cambia roles ni envía mensajes.
- No procesa pagos, saldos personales, deuda, becas individuales ni expedientes privados; solo puede explicar documentos publicados que estén indexados y autorizados.
- No enseña ni resuelve el contenido de ejercicios; no es un buscador web general ni navega arbitrariamente Internet.
- No procesa PDF escaneados por OCR, DOCX, hojas de cálculo, audio o video en la canalización de ingesta documentada.
- No promete respuestas correctas para todo el universo documental; solo responde desde los fragmentos disponibles y configurados.
- No incluye cuotas/contabilidad de tokens, panel de uso, administración institucional, control editorial/aprobación de documentos ni historial persistente de chat dentro de RAG.
- No incorpora balanceo de proveedores en la ruta activa; no hay fallback automático de Gemini a Bedrock/Ollama ni de DeepSeek a otro LLM. Existen módulos/configuración heredados de embeddings locales/AWS, pero no forman parte del `QueryService`/`EmbeddingRouter` activo.

## 4. Requerimientos no funcionales y evaluación

| ID | Atributo | Estado comprobable | Brecha/condición |
|---|---|---|---|
| NFR-01 | Seguridad de autorización | Filtro previo de cursos; firma ligada al cuerpo; validación de plan tanto en RAG como Moodle; URLs construidas/permitidas por Moodle | El claim `jti` es requerido, pero RAG no mantiene registro de consumo/replay. Un mismo token/cuerpo podría repetirse dentro de su vigencia; actualmente son consultas de lectura, aunque podrían repetir llamadas y costo. |
| NFR-02 | Privacidad | Logs no incluyen preguntas, fragmentos, vectores ni credenciales; las claves usan `SecretStr` y quedan server-side | La consulta/historial que requiere interpretación viaja a DeepSeek; los embeddings/envíos documentales viajan a Gemini. Faltan una política aprobada de tratamiento, retención, residencia, respuesta a incidentes y contrato institucional aplicable. |
| NFR-03 | Integridad de fuentes | Hash del documento; transacción de versión/fragmentos; inserción solo tras validar vectores; clave estable e ingesta repetible | El PDF original vive en el filesystem de administración/inbox y no hay un repositorio editorial con aprobación, caducidad y propietario de contenido implementado. |
| NFR-04 | Exactitud/abstención | JSON estricto, citas mapeadas a fuentes reales, comprobar vigencia del corpus tras generación, evaluación con 5 negativas | Corpus de 41 preguntas pequeño; comparación de hechos parcialmente literal; revisión semántica manual no independiente. |
| NFR-05 | Rendimiento | Medidas secuenciales RAG p50 2,629 s / p95 3,016 s; flujo Moodle p50 3,49 s / p95 8,13 s | No mide concurrencia, carga, tamaño de cola, degradación prolongada ni percentiles por intent/proveedor en producción. |
| NFR-06 | Disponibilidad/resiliencia | Retries acotados para 408/429/5xx y errores de conexión/timeout; salud de base; errores tipificados | Sin SLA, despliegue redundante, worker/cola, control de tasa, alerta, circuit breaker activo en ruta Gemini, proveedor alternativo, ni estrategia operativa de mantenimiento. `/health` prueba la base/esquema, no disponibilidad de DeepSeek/Gemini. |
| NFR-07 | Capacidad y límites | Entrada ≤1.000 caracteres; contexto hasta cuatro turnos; fragmentación/PDF limitados; hasta cuatro fragmentos consultados | Sin prueba de carga ni cuotas por usuario; solicitudes externas sin presupuesto de tokens explícito; el tiempo máximo configurado de proveedor es 120 s y puede acumularse con reintentos. |
| NFR-08 | Portabilidad | Docker Compose; Python ≥3.12; esquema SQL versionado; contrato OpenAPI | Compose local usa credenciales de desarrollo, DB en volumen local, sin despliegue IaC, TLS/ingress, secretos administrados o configuración de entorno productivo. |
| NFR-09 | Observabilidad | Log JSON: UTC, operación, estado, milisegundos, request ID y código seguro | No hay métricas exportables, tokenización, consumo/costo, usuario/categoría, seguimiento distribuido, retención/alertas ni dashboard. Se evita registrar contenido deliberadamente. |
| NFR-10 | Mantenibilidad | 18 módulos de pruebas, Ruff, contratos Pydantic, migraciones y CI | El workflow se llama “Validar Sprint 1” y referencia `compose.ollama.yaml`/`compose.aws.yaml`, archivos que no están en el checkout actual. Debe actualizarse y verificarse antes de usar CI como gate vigente. |
| NFR-11 | Recuperación | PostgreSQL en volumen Docker y transacciones de escritura | No se encontró plan automatizado de backup/restore, RPO/RTO, retención de copias ni prueba periódica de recuperación. |

### 4.1 Restricciones documentales actuales

- Tamaño PDF máximo: 20 MiB. Páginas máximas: 300. Fragmentos máximos: 1.000.
- Fragmentación objetivo: 2.000 caracteres, solapamiento 200; se mantiene la página que aportó cada texto.
- PDF cifrado/rechazado, corrupto o sin texto útil no se indexa. Páginas sin texto se informan; el servicio no OCRiza.
- Tipos admitidos: `REGLAMENTO`, `PROCEDIMIENTO`, `SILABO`, `GUIA`, `OTRO`. Alcances: `institutional`, `course`.
- Embedding de consulta y documentos debe coincidir exactamente en proveedor, modelo, revisión y dimensiones. Un espacio incompleto falla cerrado y bloquea respuestas documentales.
- Evidencia: top 4 fragmentos; selección de hasta 3 pasajes. En consultas simples la selección se limita a un pasaje. El texto final cita la evidencia y agrega ficha documental, fragmento y páginas.

## 5. API, datos y operación

### 5.1 Rutas

| Método/ruta | Acceso | Propósito y respuesta |
|---|---|---|
| `GET /health` | Sin autenticación | Estado de API y PostgreSQL/esquema; 200 o 503. No contacta proveedores de modelos. |
| `POST /api/v1/chat/interpret` | Bearer Moodle firmado | Recibe pregunta, máximo cuatro turnos, estado y reloj/zona horaria; devuelve plan JSON de operaciones permitidas. |
| `POST /api/v1/chat/query` | Bearer Moodle firmado | Recibe pregunta, plan opcional, contexto académico y cursos; devuelve respuesta, fuentes, indicador de insuficiencia y request ID. |
| `GET /demo` | Sin autenticación si activado | UI de pruebas para corpus documental institucional. |
| `POST /api/v1/demo/chat/query` | Sin autenticación si activado | Prueba documental sin identidad/cursos Moodle. No debe quedar habilitada en red compartida. |
| `GET /docs`, `/openapi.json` | FastAPI por defecto | Esquema/Swagger; no se deshabilita actualmente en la factoría FastAPI. Revisar exposición en producción. |

El límite de consulta es 1.000 caracteres. Errores cubren validación (422), autenticación (401), alcance (403), falta de configuración/DB/índice (503), salida/embedding inválido (502), timeout de proveedor (504) y corpus modificado concurrentemente (409). El contrato exacto está descrito en el README y modelos de `query.py`.

### 5.2 Modelo de persistencia RAG

El esquema contiene versión de migración, catálogo de tipos, documentos y versiones, fragmentos con páginas, proceso de indexación, espacio embedding, embedding asociado a cada fragmento, cursos Moodle activos y relación documento-curso. Las actualizaciones reemplazan fragmentos/vectoriales de la versión anterior dentro de transacción; fallos de proveedor o DB no deben destruir la versión vigente. El PDF original no se guarda como BLOB en la base: se mantiene en la ruta de ingesta y el contenedor recibe `data/inbox` montado de solo lectura.

La búsqueda establece transacción de solo lectura/repetible, filtra documentos visibles y calcula distancia coseno en pgvector. Los documentos institucionales se comparten entre usuarios autenticados; los documentos de curso requieren que el curso figure en claims firmados, catálogo activo y asignación del documento. La fuente vuelve a comprobarse contra su versión antes de exponer respuesta.

El corpus de demo versionado incluye once registros institucionales: matrícula, reglamento académico, trámites documentarios, calendario 2026-II, biblioteca, bienestar estudiantil, servicios digitales, becas y apoyos, integridad académica, accesibilidad e iniciación en investigación. Este conteo proviene de `demo/corpus.json`; no es un conteo vivo de `documento` porque la base no estaba disponible durante esta inspección. El proyecto Moodle agrega materiales/cursos de demostración y puede ingerir documentos asociados a curso por separado.

### 5.3 Configuración observada y ejecución local

Se confirmó de forma segura la presencia local de los valores de configuración requeridos (sin leer ni mostrar claves): DeepSeek, Gemini, secreto compartido y URL de base. El modelo configurado es `deepseek-flash`; el embedding, `gemini-embedding-001`/768. `LOCAL_DEMO_QUERY_ENABLED=true` está activo en `.env` local. Los puertos Compose están ligados a `127.0.0.1`.

En la inspección del informe ambos Compose estaban detenidos y `/health` no conectaba. Por tanto, el informe no afirma que ahora el proveedor responda ni que la base local esté sana. El `index-status` no pudo consultarse en esta inspección; el inventario del corpus que sigue se deriva de los archivos de demo y reportes versionados, no de un recuento en vivo de la base.

Comandos reproducibles y de operación: [README del servicio](../README.md). Los principales son `docker compose up -d db`, `rag prepare-demo`, `docker compose up --build -d api`; `/health` comprueba DB, `rag index-status` cobertura. Para Moodle completo se utiliza el procedimiento del repositorio superior; los despliegues locales deben mantener sus volúmenes al apagar (`docker compose down`, sin `-v`).

## 6. Inventario de pruebas automatizadas

### 6.1 Tipos implementados

La suite Python contiene 18 módulos y combina tests puros, componentes aislados, fixtures, una suite PostgreSQL marcada `integration`, pruebas de navegador simuladas y una evaluación DeepSeek real aparte.

| Módulo | Área cubierta |
|---|---|
| `test_academic_answers.py` | Formato de categorías académicas, estado, fecha en español y fecha inválida/no rellenada |
| `test_api_auth.py` | Firma JWT, issuer/audience, expiración, cuerpo firmado, cursos y solicitudes protegidas |
| `test_api_config_cli.py` | Contratos HTTP, configuración, CLI y códigos de error |
| `test_conversation.py` | Modelos de plan, validaciones de intención/alcance, seguimiento, historial y estructura de salida |
| `test_deepseek.py` | Contrato Chat Completions, respuesta JSON, credenciales y errores/reintentos del proveedor |
| `test_demo_browser.py` | Estados de UI, bloquear duplicados, fallos, recuperación y render seguro con navegador simulado |
| `test_demo_setup.py` | Preparación reproducible de la demo, PDF/corpus y reejecución |
| `test_document_evidence.py` | Selección y validación de citas/pasajes, instituciones y evidencia insuficiente |
| `test_documents.py` / `test_pdf_extraction.py` | Hash, metadatos, texto por página, fragmentos, PDF dañado/cifrado/límites y ausencia de OCR |
| `test_embeddings.py` / `test_gemini.py` | Tipo/forma/dimensión de vector, Gemini REST, tareas de embedding y errores/reintentos |
| `test_ingestion.py` | Validación del scope/curso, idempotencia, actualización transaccional y provider |
| `test_local_embeddings.py` | Código heredado/de compatibilidad de Ollama/Bedrock y circuit breaker; no prueba que esa ruta esté activa en el servicio actual |
| `test_observability.py` | Forma de evento de log sin contenido sensible |
| `test_query.py` | RAG, referencias, abstenciones, mezcla de fuentes, autorización y errores de consulta |
| `test_repository_integration.py` | DB real: migraciones, ingesta, versionado/borrado, recuperación, filtros, rollback, concurrencia y reindexación |
| `test_weekly_plan.py` | Reglas de semana, tareas, disponibilidad, zona horaria, prioridades y parcialidad |

CI actual está en [.github/workflows/ci.yaml](../.github/workflows/ci.yaml): instala Python 3.12, Postgres pgvector y Chromium; ejecuta Ruff, Pytest con `--require-complete` y `docker compose config`. Su referencia a los Compose antiguos no coincide con los archivos presentes, así que el estado de CI no debe suponerse verde hasta corregir esa configuración.

### 6.2 Evidencia de ejecución disponible

| Validación | Resultado guardado/último observado | Alcance y límites |
|---|---|---|
| Ruff | Sin errores | Análisis estático acotado a reglas `E`, `F`, `B`; no es análisis de seguridad completo. |
| Pytest RAG | 260 pasaron, 14 omitidos | Las 14 omisiones corresponden a integración DB por no definir `TEST_DATABASE_URL`; ejecución normal pasa, pero `--require-complete` la marca incompleta. |
| PHPUnit plugin Moodle | 53 pruebas, 243 aserciones, aprobadas | Cubre el puente Moodle, no reemplaza aceptación de una instancia productiva. |
| Evaluación documental DeepSeek | 41 consultas, `complete: true`, 35/36 positivas automáticas, 5/5 negativas, documento esperado 36/36 | p50 2,629 s; media 2,666 s; p95 3,016 s; máximo 3,081 s; 109,301 s total secuencial; 0,375 consultas/s secuenciales. Informe: [evaluation-deepseek-results.json](evaluation-deepseek-results.json). |
| Revisión semántica de 36 positivas | El informe registra ningún error factual observado en esta muestra y explica P19 | El comparador automático marcó P19 incorrecta porque esperaba “gratis/sin costo” y la respuesta usó “gratuita”; no fue revisión externa/independiente. |
| Chat Moodle de extremo a extremo | 72 consultas, completo, sin reintentos; p50 3,49 s, p95 8,13 s, máximo 8,35 s según el informe de validación | Incluye interpretación y lecturas de Moodle/RAG; secuencial y sin carga concurrente. Evidencia: [ticket06-browser.json](../../.scratch/asistente-conversacional/ticket06-browser.json). |
| Navegación Moodle | 7 escenarios reportados como completos | Confirma permisos/destinos/casos de navegación; evidencia: [navigation-browser.json](../../.scratch/asistente-conversacional/navigation-browser.json). |

Estos datos son ejecuciones locales de demostración y no implican continuidad del servicio. No se debe comparar p95 RAG con p95 Moodle como si midieran el mismo recorrido.

### 6.3 Pruebas que faltan o requieren reforzarse

**Bloqueantes antes de producción**

1. Ejecutar toda la suite de integración DB con un PostgreSQL/pgvector aislado, no vacío compartido ni producción; definir `TEST_DATABASE_URL` y lograr `--require-complete` sin omisiones.
2. Corregir/ejecutar la CI actual: eliminar referencias a Compose ausentes, fijar matriz de versiones y publicar artefacto de resultado. Añadir workflow para PHP/plugin si el repositorio Moodle no lo valida en su propia CI.
3. Prueba de carga concurrente (usuarios, p50/p95/p99, throughput, errores 429/5xx, conexiones DB, costo por intent) con límites presupuestarios, sin usar datos personales.
4. Pruebas de resiliencia de extremo a extremo al perder DeepSeek, Gemini, DB, red/DNS, timeout, 429 sostenido, actualización/eliminación de documento durante consulta y reintento; establecer recovery y degradación comprensible.
5. Revisión de seguridad independiente: replay de JWT/`jti`, rotación de secreto, brute force/DoS, límites de tasa, exposición de `/demo`, `/docs`/OpenAPI, TLS/ingress, roles de administración e inspección de dependencias/imagen.
6. Revisar contratos y políticas de datos de DeepSeek y Google para prompts, datos académicos y fragmentos; aprobar qué clases de información pueden salir a servicios externos, retención, región, borrado y notificación.

**Alta prioridad**

- Ampliar conjunto de evaluación con preguntas reales anonimizadas, cursos múltiples, idiomas/errores ortográficos, temporadas y documentos contradictorios/obsoletos; separar evaluación de embeddings/retrieval, fidelidad de respuesta, citas y abstención. Añadir evaluación por docente/experto que no haya escrito los prompts.
- Comprobar relevancia de recuperación (Recall@k, MRR/nDCG) además de si el generador encontró hechos esperados; medir retrieval por separado de generación.
- Tests de propiedades/fuzz para JSON/modelos, PDFs hostiles, Unicode, prompt injection en PDF, referencias institucionales adversariales y contenido sensible.
- Pruebas de interfaz: accesibilidad WCAG, teclado/lector de pantalla, idioma, viewport móvil, fuentes/citas, enlaces internos y regresión visual.
- Reindexación/backup/restore: pérdida de volumen, recuperación temporal, migración a vector nuevo y actualización de modelo, rollback, eliminación y consistencia de ACL de cursos.
- Agregar tests y telemetría de costo/uso, con límites por usuario y alertas de presupuesto. Instrumentar fases `interpret`, embedding, retrieval, evidencia y total, sin registrar prompts.
- Probar fallos parciales del flujo mixto y expiración/replay durante la comunicación Moodle→RAG; cuantificar duración de aserción vs. tiempo de proveedor.

**Criterio de completitud:** la batería actual es sólida para contratos y una demo, pero no cubre capacidad, continuidad, riesgo de tratamiento de datos ni gobierno operativo.

## 7. Gastos y método de estimación

### 7.1 Qué puede afirmarse

No se puede calcular una factura mensual de esta instancia con los datos del repositorio: no hay telemetría de tokens de entrada/salida/cache, inventario de volumen vivo consultable en este corte, volumen de usuarios/consultas, ni acceso a facturación de DeepSeek/Google. Los registros actuales conservan operación, duración, estado, request ID y código; excluyen contenido y **no** guardan consumo facturable por modelo.

El Compose local crea PostgreSQL/pgvector y API en Docker con puertos de localhost y volúmenes locales. No hay un cargo de infraestructura AWS inherente al flujo activo. El costo del equipo, electricidad, almacenamiento y tiempo de operación no se mide en código. Una instalación cloud sumaría cómputo, base administrada, almacenamiento, respaldos, transferencia, monitoreo, DNS/TLS y soporte; no hay proveedor/tamaño definido para presupuestarlo.

### 7.2 Generación DeepSeek

El precio oficial consultado para `deepseek-flash` (V4.1 Flash) es por millón de tokens, varía entre horario pico y no pico y separa cache hit/miss de entrada. Al 22-oct-2026, DeepSeek publica:

| Tokens DeepSeek | Fuera de pico | Pico |
|---|---:|---:|
| Entrada, cache hit / 1M | USD 0,003 | USD 0,006 |
| Entrada, cache miss / 1M | USD 0,15 | USD 0,30 |
| Salida / 1M | USD 0,60 | USD 1,20 |

Pico: lunes a viernes, 01:00–04:00 y 06:00–10:00 UTC salvo festivos oficiales chinos; el resto se tarifa como fuera de pico según la página de DeepSeek. Fórmula de estimación:

```text
C_DS = (input_cache_hit × tarifa_hit
      + input_cache_miss × tarifa_miss
      + output_tokens × tarifa_output) / 1.000.000
```

El flujo usa varias llamadas de interpretación en ciertas intenciones y otra selección para evidencia; por tanto, **una interacción de usuario no equivale necesariamente a una llamada ni a un único prompt**. Para obtener costo real por conversación se necesitan uso por respuesta de proveedor y distribución por intención/cache. Fuente: [tarifas y modelo DeepSeek](https://api-docs.deepseek.com/quick_start/pricing/); el alias activo `deepseek-flash` apunta a V4.1 Flash según [anuncio oficial del modelo](https://api-docs.deepseek.com/news/news260910/).

### 7.3 Embeddings Gemini

El servicio activo llama Gemini Developer API (`generativelanguage.googleapis.com`) con `gemini-embedding-001`: se vectoriza cada fragmento durante ingesta/reindexación y cada pregunta documental antes de buscar. No se usa Gemini para redactar el chat. La tabla pública actual de precios de Gemini Developer API muestra `gemini-embedding-2`, pero no una tarifa inequívoca para el modelo configurado `gemini-embedding-001`; por eso este informe no adjudica un monto a la facturación de la clave configurada. Google publica para Gemini Enterprise Agent Platform una tarifa genérica de Gemini Embedding de USD 0,00015 por 1.000 solicitudes online y USD 0,00012 por 1.000 solicitudes batch. Es otro producto y no especifica aquí el endpoint Developer API/modelo `gemini-embedding-001`; **no debe aplicarse a esta factura sin confirmar la tarifa/capa de facturación de la cuenta**. La página de precios del Developer API también distingue Free (contenido puede usarse para mejorar productos) y Paid (contenido no se usa con ese fin); hay que confirmar el nivel efectivo de la clave antes de enviar datos institucionales. Ver [precios Gemini Developer API](https://ai.google.dev/gemini-api/docs/pricing), [precios de Gemini Enterprise Agent Platform](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing) y [documentación de embeddings](https://ai.google.dev/gemini-api/docs/embeddings).

Google indica que `gemini-embedding-001` permanece disponible hasta el 14 de mayo de 2028 y recomienda planificar migración; el cambio de modelo exige reindexar el corpus entero en un espacio nuevo antes de habilitar consultas. Fuente: [calendario oficial de deprecaciones](https://ai.google.dev/gemini-api/docs/deprecations).

### 7.4 Costos no activos y datos necesarios

- AWS Bedrock/Titan y Ollama tienen piezas de compatibilidad histórica, pero la configuración actual usa Gemini para embeddings; no presupuestar Bedrock como consumo del camino ordinario.
- DeepSeek Search/Fetch no se usa por la aplicación; sus tarifas no son parte del costo por consulta RAG.
- Para calcular un presupuesto mensual hacen falta, como mínimo: usuarios activos, chats/usuario/mes, mezcla de intents, tokens de cada fase, tasa real de cache, tokens de PDFs a ingresar/reindexar, tarifa de cuenta/API, cuota gratuita/créditos, precio de hosting y plan de backup/retención.
- La mejora recomendada es capturar de forma segura `usage` del proveedor (input/output/cache) y duración por etapa; agregar agregados diarios por modelo/intención y alertas. No guardar contenido o claves para medir costos.

## 8. Riesgos, controles y decisiones pendientes

| Riesgo | Impacto | Control existente | Trabajo requerido |
|---|---|---|---|
| API demo sin autenticación habilitada | Cualquier usuario que alcance la instancia puede preguntar contra corpus institucional | Puertos locales; demo configurable | Desactivar fuera de desarrollo y probar que el proceso de despliegue imponga `false` |
| Datos académicos/institucionales hacia proveedores | Exposición o tratamiento no permitido según política institucional | Envío server-side; filtro por curso; logs sin contenido | Aprobación de gobernanza, contrato, minimización y política de datos antes de conectar campus real |
| Repetición de aserción firmada | Repetir lectura/costo dentro de 120 s | HMAC, hash del cuerpo, exp, `jti` obligatorio | Registrar y rechazar `jti` usados hasta expirar; definir idempotencia/reintentos legítimos |
| Disponibilidad dependiente de dos APIs externas | Preguntas documentales requieren Gemini y DeepSeek | Retries y errores claros; no fallback silencioso | Monitorizar por fase, estrategia de cuota/alerta y modo degradado aprobado |
| Cambio/deprecación de embedding | Índice no compatible o consultas detenidas | Identidad del espacio y cobertura estricta; reindexación explícita | Planear y ensayar migración a modelo sucesor mucho antes de mayo 2028 |
| Contenido/PDF hostil o con instrucciones | Respuesta manipulada o selección indebida | Pasajes no confiables, selección cerrada, cita literal, validadores | Red team y corpus adversarial continuo; no interpretar estos controles como garantía total |
| Exposición accidental de demo/docs al publicar puertos | Acceso no autenticado y superficie API adicional | Compose liga a localhost en desarrollo | Revisión de ingress/TLS, ACL de red, cierre de demo y docs antes de deploy |
| Ingesta desactualizada o equivocada | Información institucional incorrecta | Clave/versionado/hash, registro de páginas, categorías | Flujo de propietario, revisión, vigencia, aprobador y calendario de caducidad |
| Falta de recuperación/observabilidad operativa | Interrupción larga o costo inesperado | Health de DB, request ID y logs sin contenido | Backups probados, alertas, SLA/RTO/RPO y métrica de uso/costo |

### Decisiones de salida a producción pendientes

1. Responsable institucional de cada fuente y autoridad para aprobar, retirar y reindexar contenido.
2. Política para PII, calificaciones, datos de cursos y documentos reservados antes de enviarlos a proveedores externos.
3. Si el entorno de producción permitirá embeddings externos Gemini y el modelo DeepSeek, con límites regionales/contractuales acordados.
4. Entorno objetivo, disponibilidad, usuarios concurrentes, latencia y presupuesto mensual máximo.
5. Rotación del secreto y defensa anti-replay; protección de endpoints demo/OpenAPI; rate limit y cuotas.
6. Repositorio de backups, pruebas de restore y retención.
7. Pipeline de CI/CD vigente con plugin Moodle, análisis de dependencias/imagen, gates y artefactos de evaluación.
8. Política ante baja confianza, ausencia de evidencia y discrepancias entre Moodle y documentos institucionales.

## 9. Plan de trabajo sugerido

| Prioridad | Entregable | Evidencia para cerrar |
|---|---|---|
| P0 | Corregir CI y recuperar 14 pruebas DB omitidas | Ejecución `--require-complete` en CI actual con PostgreSQL/pgvector y Chromium |
| P0 | Cerrar demo, docs y replay en perfil de despliegue | Pruebas negativas sobre configuración desplegada y `jti` de un solo uso |
| P0 | Decisión de privacidad y autorización de proveedores | Aprobación institucional documentada antes de introducir datos reales |
| P1 | Instrumentación de fases y consumo de tokens/costo | Reporte mensual agregado, sin contenido, por modelo e intención |
| P1 | Prueba de carga y fallos | Informe p50/p95/p99, concurrencia, coste/error y límites probados |
| P1 | Backup/restore y rotación de secretos | Ensayo reproducible y RPO/RTO acordados |
| P1 | Evaluación ampliada e independiente | Conjunto versionado, métricas retrieval/answer/citation/refusal y revisión experta ciega |
| P2 | Flujo editorial y observabilidad de documentos | Responsable, aprobación, fecha de vigencia, retiro, reindexación e historial auditado |
| P2 | Migración de embeddings previa a deprecación | Reindexación paralela completa, comparativa de retrieval y cambio controlado |

## 10. Fuentes y trazabilidad

### Fuentes del repositorio

- [README y operación RAG](../README.md)
- [Configuración](../src/rag_service/config.py), [API](../src/rag_service/api.py), [contratos conversacionales](../src/rag_service/conversation.py), [consulta/recuperación](../src/rag_service/query.py)
- [Autenticación Moodle](../src/rag_service/moodle_auth.py), [evidencia documental](../src/rag_service/document_evidence.py), [PDF](../src/rag_service/documents.py), [ingesta](../src/rag_service/ingestion.py), [repositorio](../src/rag_service/repository.py)
- [Resultados de evaluación real](evaluation-deepseek-results.json), [validación conversacional y navegación](../../docs/validacion-deepseek.md), [suite Pytest](../tests), [CI](../.github/workflows/ci.yaml)

### Fuentes oficiales de proveedores

- DeepSeek, [Modelos y precios](https://api-docs.deepseek.com/quick_start/pricing/) y [anuncio de V4.1 Flash](https://api-docs.deepseek.com/news/news260910/).
- Google, [precios Gemini Developer API](https://ai.google.dev/gemini-api/docs/pricing), [embeddings Developer API](https://ai.google.dev/gemini-api/docs/embeddings), [precios de Gemini Enterprise Agent Platform](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing) y [deprecaciones](https://ai.google.dev/gemini-api/docs/deprecations).

## 11. Declaración de limitaciones

Este documento se basa en el código, configuración, reportes y resultados locales disponibles al 22 de octubre de 2026. Se observaron cambios sin confirmar en los repositorios Moodle/RAG; por ello, los hallazgos describen el árbol de trabajo y no deben asociarse a un release inmutable. La disponibilidad de contenedores se comprobó en el momento de redactar y estaban detenidos. No se accedió a facturas, métricas del panel de proveedores, datos de producción ni políticas institucionales. Los precios cambian; verificar las páginas oficiales y el panel de cada cuenta antes de presupuestar o contratar.
