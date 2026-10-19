# Verificación del asistente conversacional

Fecha: 2026-10-06. Estado: ejecución cerrada por solicitud del usuario; aceptación final pendiente.

## Entorno y contrato

Moodle local 5.3dev (Build 20260911), PHP 8.3.35, PostgreSQL 17.11;
RAG FastAPI y Ollama con qwen2.5:3b
(revisión `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`). La versión desplegada fuera de este entorno
no está confirmada. Se mantuvo el modelo y la frontera del ADR-0001.

Moodle interpreta mediante su cliente servidor firmado, valida el plan propuesto,
autoriza y consulta las operaciones nativas y envía resultados firmados al RAG.
El modelo no decide identidad, permisos ni ejecuta SQL, URLs o escrituras.
La interpretación tiene como máximo dos llamadas: clasificación y extracción de
argumentos; una consulta documental puede añadir hasta dos llamadas acotadas: extracción de
restricción institucional y selección de evidencia. El máximo combinado es cuatro.
Saludo, cortesía, despedida y capacidades no recuperan documentos ni datos académicos.

## Evidencia por ticket

| Ticket | Comprobación | Evidencia |
| --- | --- | --- |
| 01 | Contratos cerrados, firma del cuerpo, reloj y zona Moodle, rechazo de operaciones no permitidas | `test_conversation.py`, `conversation_test.php`, suites de autenticación existentes |
| 02 | Reformulación/contexto: test_model_receives_reformulation_context_before_any_moodle_read; referencia ambigua: test_unnamed_task_reference_requires_native_disambiguation_without_document_lookup; disponibilidad: test_unknown_availability_is_extracted_without_copying_previous_schedule y test_semantic_availability_is_session_scoped_and_cleared; llamadas y errores: conteo de hasta 2 en la regresión y validador real, test_gemini_maps_timeout_and_invalid_json; Gemini real: ticket02-live-validation.json | suites Python/Moodle y ocho interpretaciones reales con datos sintéticos |
| 03 | Lecturas con capacidades reales, matrícula, grupos, entregas, estados y prórrogas; guía local verificada | `academic_context_provider_test.php`, `conversation_test.php`, `docs/portal/moodle-5.3dev-guia.md` |
| 04 | Saludo/exclusión: test_social_and_blocked_responses_never_retrieve_documents; confirmación: test_teacher_confirmation_is_direct_and_bounded_by_visible_data; citas: test_sources_come_from_database_and_citations_are_present y test_missing_inline_citation_is_added_from_valid_sources; ejemplos/salida inválida: test_unsupported_example_facts_and_document_instructions_are_not_published y test_invalid_citations_are_rejected y test_chat_invalid_response_is_controlled; cambio de tema: ticket04-browser.json | suites Python y recorrido integrado Moodle/Gemini |
| 05 | Pendientes antes de disponibilidad, agregación de 25 tareas, intervalos, domingo, zona, vencidas/borradores/sin fecha, datos parciales y cero tareas | `conversation_test.php`, `test_weekly_plan.py`, pruebas nativas de prórrogas, recorrido real `ticket05-browser.json` |
| 06 | Recorridos semánticos reales, acceso por cuenta, inyección directa/documental y borrado de sesión | `dev/moodle/smoke_browser.py`, suites de contratos/sesión y reporte local |
| 07 | Interfaz clara, sugerencias iniciales, mensaje inmediato, estado accesible de espera, móvil y envío Moodle intacto | `dev/moodle/smoke_browser.py --ticket07`, `ticket07-browser.json` |

## Comprobaciones automáticas

- RAG: **242 passed**, sin pruebas omitidas, con `--require-complete` y PostgreSQL real (2026-10-06).
- Moodle: **42 tests, 209 assertions**, sin fallos (2026-10-05); código nativo sin cambios desde esa ejecución.
- Ruff y `git diff --check`: sin errores.
- Advertencia existente de deprecación Starlette/httpx en el cliente de pruebas;
  no representa un fallo de las pruebas ni del chat.

Comandos reproducibles desde la raíz:

```bash
TEST_DATABASE_URL=postgresql://rag:rag_local_dev@127.0.0.1:55432/rag_sprint2_tests rag-service/.venv/bin/python -m pytest rag-service/tests -q --require-complete
docker compose -f compose.moodle.yaml exec -T moodle vendor/bin/phpunit --testsuite local_acadassistant_testsuite
rag-service/.venv/bin/ruff check rag-service/src rag-service/tests dev/moodle
rag-service/.venv/bin/python dev/moodle/smoke_browser.py
```

Los últimos logs quedan en `.local/conversational-pytest.log`,
`.local/conversational-phpunit.log` y `.local/conversational-browser.log` y `.local/conversational-final-segment.log`.
Los progresos de cada segmento y sus latencias quedan en los archivos locales
indicados abajo; son artefactos ignorados por Git. No hay reporte actual de
aceptación integral satisfactoria.

## Estado final de esta ejecución

La ejecución se cerró el 2026-10-06 cuando el usuario pidió terminar el proceso.
Código actual: `51fb68260` en `main`; API local reconstruida con esa versión.
No se publicó ni desplegó fuera del entorno local.

El intento integral con `c51af1f11` verificó **56 consultas** antes de detenerse
con un error en «En Universidad Otra, ¿qué cursos tengo y cuál es la nota mínima?».
El separador confundía el prefacio institucional con una petición independiente.
La corrección `51fb68260` conserva comas y signos de apertura internos; su
regresión está incluida en las **242 pruebas RAG** que pasan sin omisiones.

El tramo final se repitió desde una conversación limpia con `51fb68260`.
Pasaron las preguntas mixtas cursos/norma y tareas/código de tutoría, la norma
institucional, la consulta de otra universidad sin atribuirle la nota 11, el
rechazo del documento restringido y la expiración real de la sesión Moodle.
La siguiente consulta falló semánticamente:

- Consulta: «¿A qué hora es la tutoría del curso Algebra 101?».
- Esperado: horario documental de tutoría, martes a las 16:00, con su fuente.
- Observado: calendario de la tarea Ejercicios de ecuaciones, vencimiento
  `2026-10-12 17:19`, sin responder el horario solicitado.

El tramo final terminó con código **1**. El reporte de progreso está en
`.local/conversational-final-progress.json` y el log en
`.local/conversational-final-segment.log`. La primera parte está preservada en
`.local/conversational-first-segment.json`. No hay un reporte combinado de
aceptación satisfactoria actual y no se presenta una ejecución integral con
código 0. Las comprobaciones posteriores de logout, otras cuentas y paginación
no se ejecutaron en ese tramo; sus pruebas y focos anteriores siguen documentados,
pero no sustituyen la aceptación final pendiente.

Los tickets 02–06 conservan `Status: in-progress`. El siguiente trabajo debe
resolver la clasificación documental del horario de tutoría y completar las
comprobaciones restantes. No es necesario repetir los ciclos de ajuste cerrados
sin una causa concreta.

## Revisión

Comparación acordada: `1cf28883be6e550f7c1d3a3805afbc7f5a45b1c1`.
Revisión paralela de estándares y de spec. Los hallazgos sobre referencia pronominal
docente, discrepancia de calendario y conservación del curso del plan fueron corregidos
y revalidados. También se corrigieron selección de solicitudes pendientes,
conservación de semanas explícitas, consultas independientes del plan y alcances
por curso. Las revisiones incrementales de esos cambios terminaron sin hallazgos
de código pendientes. El resultado final distingue **Standards: 0 hallazgos**
de **Spec: 1 hallazgo de aceptación pendiente**: la consulta documental de horario
de tutoría selecciona el calendario de tareas. Afecta los tickets 02 y 04 e
impide cerrar el ticket 06. No hay evidencia de ampliación de permisos.

La selección de una tarea después de una aclaración utiliza identificadores nativos
guardados temporalmente; Moodle revalida actividad, participante y permisos en cada
lectura. La referencia seleccionada se reconstruye desde la fila nativa reautorizada, sin
acumular preguntas anteriores. La segunda extracción distingue un seguimiento
de un nuevo alcance y puede corregir el indicador de la clasificación inicial.
Una petición general explícita elimina el identificador y el filtro anterior. Las preguntas
mixtas conservan por separado los alcances académicos y documentales literales;
una petición excluida no aporta automáticamente filtros a una lectura permitida.
Las regresiones también cubren cláusulas cortas y categorías duplicadas del modelo.
Una etiqueta social omitida se normaliza sin habilitar lecturas; una clasificación
independiente verifica la intención del mensaje actual antes de responder.
El extractor exige estado de entregas y alcance de cursos cuando esas operaciones
se solicitan, para no heredar implícitamente pendientes o matrícula personal.
Los nombres de cursos no autorizan ni deniegan acceso: Moodle sigue decidiendo
qué documentos y datos puede consultar cada cuenta. Ante una persona identificada
por su nombre completo nativo pero no autorizada, o ante homónimos, el proveedor
no sustituye la lectura por notas propias; devuelve incompletitud y un aviso. Las
notas del consultante se identifican explícitamente como «tu calificación».

La evidencia documental selecciona claves nativas que unen fuente y texto literal.
El borrador redactado por el modelo es privado y no se publica; las respuestas
proceden de pasajes actuales del corpus autorizado. Las guías conservan párrafos
completos para no omitir pasos. Cuando el usuario nombra una institución, la
restricción extraída debe aparecer literalmente en su consulta y reduce las
fuentes a documentos que contienen ese nombre en su título o contenido.

Cinco probes adicionales con PostgreSQL y qwen2.5:3b comprobaron el código de
tutoría de Álgebra, el rechazo de una norma de otra universidad, el horario de
tutoría, la falta de guía para recuperar una contraseña y los pasos completos de
entrega. Se exploró qwen2.5:7b ante fallos previos de selección; no se completó un
benchmark de ese modelo y no se cambió la configuración. La corrección validada
usa qwen2.5:3b y vincula la selección a evidencia nativa.

La segunda llamada de interpretación verifica de forma focalizada las consultas
de docentes: unicidad, referencia literal, alcance actual o anterior y petición
documental independiente. La clasificación general no fija una confirmación
equivocada. El indicador de confirmación docente representa únicamente unicidad.
Las pruebas cubren confirmar sobre todos los cursos tras consultar uno concreto.
Las consultas simples de cursos utilizan una extracción focalizada que distingue
matrícula, acceso disponible y responsabilidad docente. Preguntar antes por sus
profesores no convierte al consultante en docente. Las consultas compuestas
conservan el extractor mixto para recuperar partes documentales omitidas por la
clasificación inicial. Un recorrido adicional comprobó cuatro variantes de
matrícula después de confirmar a Carla, más cursos y normativa en una misma consulta.

La extracción de tareas seleccionadas distingue referencias de nuevos listados;
con señales coherentes de petición independiente, no hereda el contexto de la
actividad elegida. Ante señales iniciales contradictorias, la segunda extracción
todavía puede corregirlas. Las consultas compuestas conservan la recuperación de
su parte documental. Las tres clases sociales puras también tienen ejemplos sin
lecturas para evitar añadir datos académicos al saludo o a la despedida.

Las consultas mixtas conservan lecturas académicas válidas cuando también piden
pagos personales excluidos; el indicador financiero exige comunicar ese límite.
La clasificación recibe contexto antes de decidir si la consulta es un seguimiento.
La extracción de una petición independiente omite filtros e historial anteriores.
Si se propone leer notas, la segunda extracción distingue resultados de una persona
de requisitos aprobatorios publicados antes de ejecutar la lectura en Moodle.
Retirar una lectura de notas errónea conserva las otras operaciones clasificadas.
Un recorrido focalizado adicional pasó seis consultas reales: cursos, dos variantes
de cursos con pagos, cursos con norma institucional, nota propia y nota visible
para un docente. No sustituye el recorrido completo de aceptación.

## Límites del resultado

La identificación nativa de participantes usa nombres completos y un catálogo
acotado a 500 matriculados por curso. No resuelve todos los alias o nombres
abreviados; si termina consultando datos propios, la respuesta los identifica
explícitamente. No se atribuyen esas notas a una identidad ajena no resuelta.

La guía cubre consultar una actividad Assignment y preparar su entrega mediante
Add submission y Save changes en el portal local; guardar puede dejar un borrador.
No se realizó una entrega para verificarla y no se atribuyen pasos de recuperación
de contraseña, pagos o administración a esta guía.

Las semanas absolutas se aceptan con fecha ISO (`AAAA-MM-DD`); otras expresiones
ambiguas piden precisar la semana. Los horarios se declaran con horas enteras.

La restricción institucional usa nombres literales del documento; no resuelve
automáticamente alias ni garantiza interpretación perfecta de referencias ambiguas.

Las metas de carga siguen aplazadas; se registran latencias observadas del flujo
local, sin afirmar una capacidad de producción. Los ataques cubiertos comprueban
las fronteras y el tratamiento de contenido no confiable, sin garantizar protección
absoluta contra toda inyección. Pagos personales, tutoría de contenidos, escrituras
y conversaciones persistentes permanecen fuera del alcance acordado.

## Migración de modelos a Gemini (2026-10-19)

La API RAG usa `v1beta/models/gemini-flash-latest:generateContent` para interpretación,
selección de evidencia y respuestas. `GEMINI_API_KEY` se lee como secreto del servidor;
las solicitudes verifican salida JSON estructurada y no habilitan fallback a modelos locales.
Las preguntas y los fragmentos usan `gemini-embedding-001` con tareas `RETRIEVAL_QUERY` y
`RETRIEVAL_DOCUMENT`, respectivamente, y 768 dimensiones.

La migración SQL 004 convierte la columna vectorial histórica a dimensión variable y admite
el nuevo proveedor. `rag init-db` aplica la migración; `rag prepare-gemini-index` recalcula
los vectores desde el texto almacenado, actualiza el proveedor/modelo por documento y puede
reanudarse sin recalcular documentos que ya tengan cobertura Gemini completa. Las búsquedas
fallan con índice incompleto mientras la migración del corpus no cubra todos los fragmentos.

Verificación automatizada inicial de la migración: Ruff sin hallazgos y **235 pruebas aprobadas**,
con **12 pruebas de PostgreSQL omitidas** por falta de entorno de integración. En esa ejecución
no se hizo una llamada real ni reindexación: aún no estaba configurada `GEMINI_API_KEY` y no había
servicios Docker activos. Las comprobaciones posteriores se registran abajo.
Las pruebas cubren errores de cuota, timeout y respuesta JSON inválida. La reindexación completa
y la preservación del índice anterior ante fallo aún requieren la base PostgreSQL de prueba.
Por ello, el recorrido Moodle + Gemini y la aceptación conversacional siguen pendientes; los
resultados con Ollama descritos arriba son históricos y no validan este proveedor.

### Prueba real de generación (2026-10-19)

La clave autenticó una consulta de metadatos HTTP 200 para `gemini-flash-latest`; la API anuncia
`generateContent` como método compatible. La prueba real de embeddings había respondido. En
cambio, solicitudes mínimas a `generateContent` agotaron el timeout y otra recibió HTTP 503
`UNAVAILABLE` con el mensaje de alta demanda temporal del proveedor. Una nueva solicitud desde
el cliente RAG también agotó el timeout. Por este motivo no fue posible validar una interpretación
ni una fecha con una respuesta real del modelo.

Se corrigió localmente la conversión del esquema Pydantic para retirar campos que la API Gemini
rechaza (`additionalProperties`, `title` y otros metadatos). La prueba enfocada del adaptador pasa
(6 pruebas); también pasan `test_conversation.py` (63) y `test_query.py` (53), que usan modelos
simulados y validan lógica local, incluido el reloj confiable y las fechas semanales. Estas pruebas
no sustituyen la validación semántica con Gemini real; el ticket 02 sigue en curso.

### Reintento de Gemini y revisión de lecturas autorizadas (2026-10-19)

Una nueva petición mínima desde `GeminiAPI`, con un límite de 128 tokens, recibió HTTP 503 en
1,69 segundos. El proveedor volvió a indicar alta demanda temporal para `gemini-flash-latest`.
No hubo contenido generado: la interpretación y el contexto temporal con Gemini real siguen
pendientes y el ticket 02 permanece en curso.

Se avanzó con la revisión del ticket 03. Moodle revalida acceso a cursos, visibilidad de
actividades, capacidades de calificaciones y grupos antes de construir el contexto. El cliente
revalida los cursos al firmar; RAG comprueba firma, identidad, vencimiento y hash del cuerpo, y
filtra documentos en SQL usando los cursos firmados. La guía del portal conserva su versión y
su límite explícito a actividades Assignment; no se repitió el recorrido de navegador.

Evidencia nueva:

- `pytest -q tests/test_api_auth.py tests/test_conversation.py tests/test_gemini.py`:
  **81 aprobadas**, con servicios/modelos simulados en los límites externos.
- Contrato PHP autónomo `tests/client_contract.php`: **aprobado**.
- PHPUnit nativo de Moodle `academic_context_provider_test.php`: **18 pruebas y 100 aserciones
  aprobadas** contra PostgreSQL de prueba. Cubre notas propias/ajenas, capacidades efectivas,
  grupos separados, actividades visibles, paginación y revocación de matrícula entre páginas.

Solo se inició la base Moodle necesaria para PHPUnit y se detuvo al terminar. El ticket 03
sigue en curso: faltan el recorrido integrado con Gemini y la migración/verificación del índice
documental Gemini; estas pruebas no sustituyen esas comprobaciones.

### Alternativa estable y reintentos acotados (2026-10-19)

Por autorización del usuario se probaron nombres de modelos estables anunciados por la API.
`gemini-2.5-flash` devolvió 404 (no disponible para nuevos usuarios); `gemini-3.8-flash` agotó
20 segundos y `gemini-3.1-flash-lite` devolvió 503. `gemini-3.5-flash-lite` generó realmente
`{"answer":"OK"}` en 1,96 segundos y repitió el resultado en 1,84 segundos con el formato
actualizado. El `.env` local selecciona este último; el modelo de embeddings no cambió.

El cliente usa ahora `generationConfig.responseFormat.text.schema` conforme al contrato REST
actual, en lugar del esquema OpenAPI antiguo. Esto sustituye el filtrado de metadatos descrito
en la corrección inicial: conserva `$defs`, `$ref` y restricciones originales del esquema
Pydantic. Se añadieron hasta dos reintentos por defecto para fallos transitorios, con espera
exponencial y variación aleatoria; no cambia el modelo durante un reintento.

Una primera ejecución del intérprete todavía leyó `gemini-flash-latest` y agotó tres intentos.
Tras detectar esa discrepancia, se repitió con `--model gemini-3.5-flash-lite` explícito y
**pasaron los seis casos reales**. Se confirmó al terminar que el modelo efectivo de `.env`
es Flash Lite. `gemini-live-validation.json` registra los planes, el reloj fijo y las latencias.

| Caso real | Resultado | Latencia total |
|---|---|---|
| Cursos matriculados | `academic`, `courses`, modo `enrolled` | 15,33 s |
| Esta semana | 2026-10-19 a 2026-10-25 en Lima | 18,43 s |
| Próxima semana | 2026-10-26 a 2026-11-01 en Lima | 13,30 s |
| Semana del 2026-11-02 | 2026-11-02 a 2026-11-08 | 17,42 s |
| «¿Y quiénes más?» | conserva docentes y curso del tema anterior | 20,27 s |
| «Ahora muéstrame mis cursos» | cambia a cursos y elimina la selección de tarea | 18,43 s |

El modelo real produjo los planes; el renderizador local calculó los intervalos desde esos
planes con reloj y datos sintéticos. No se ejecutaron consultas a datos de Moodle en estos casos
ni se verificó la recuperación documental o la reindexación. Los seis resultados no constituyen
aceptación integral del proyecto ni garantizan la disponibilidad futura del proveedor.

Verificación local final: **244 pruebas aprobadas, 12 de PostgreSQL omitidas**; Ruff, validación
de Compose y `git diff --check` sin hallazgos. Incluye recuperación tras 408/429/503/timeout,
agotamiento de reintentos, errores de cliente sin reintento y conservación del esquema completo.
Los tickets 02–06 conservan sus estados; quedan los demás criterios y el recorrido integrado.

### Cierre del ticket 03 con Moodle y Gemini reales (2026-10-19)

El ticket 03 queda `done`: se completan sus pendientes de índice y navegador.
Los tickets 02, 04, 05 y 06 conservan sus pendientes.

- Esquema 4, ocho documentos, veinte fragmentos Gemini de 768 dimensiones.
  Los vectores históricos de 1024 dimensiones se preservan en otro espacio.
  Repetir la preparación tarda 213 ms y no genera embeddings nuevos.
  El catálogo sincronizado contiene 25 cursos activos.
- Se corrigieron los metadatos del adaptador histórico, la validación de lotes
  incompletos y el filtrado SQL materializado antes de calcular distancias.
  La regresión reproduce la mezcla de dimensiones después de `ANALYZE`.
- La extracción usa el contrato público Gemini sin inventario local de modelos.
  El selector evalúa relevancia sobre pasajes ya autorizados por Moodle/RAG,
  sin reinterpretar frases del documento como permisos.
- Python con PostgreSQL: 259 pruebas aprobadas, ninguna omitida; incluye 14 de
  repositorio, reanudación, preservación del índice y aislamiento por curso.
- PHPUnit Moodle: 42 pruebas, 209 aserciones; contrato PHP autónomo aprobado.
  Cubre permisos efectivos, paginación y revocación entre páginas.
- Navegador real con `gemini-3.5-flash-lite`: ocho consultas, 4,16–12,61 s.
  Acceso anónimo denegado, cursos matriculados, rol declarado sin privilegios,
  notas ajenas no disponibles, guía verificada, consulta sin fuente, documento
  autorizado, nota docente y catálogo parcial explícito: satisfactorios.
  Add submission y Save changes se contrastaron con Moodle sin guardar entregas.

Artefactos: [índice](ticket03-index.json), [navegador completo](ticket03-browser.json).
Reproducción desde `rag-service`:

```sh
PLAYWRIGHT_BROWSERS_PATH=.cache/ms-playwright .venv/bin/python -u ../dev/moodle/smoke_browser.py --ticket03
```

La guía conserva su cobertura explícita de Assignment. Las comprobaciones temporales
anteriores usan reloj y datos sintéticos. El caso de tutoría y selección de tareas
pendiente pertenece a los siguientes tickets; no se declara aceptación integral.

### Cierre del ticket 04: respuesta documental tras cambiar de tema (2026-10-19)

El ticket 04 queda done. Si la primera clasificación hereda una tarea seleccionada,
la extracción focalizada ahora puede reconocer una solicitud documental independiente.
Ese plan elimina el identificador de tarea, filtros ambiguos y la marca de seguimiento;
Moodle/RAG recuperan solo el documento autorizado y las citas siguen vinculadas a esa fuente.

La regresión de tests/test_conversation.py primero falló porque el contrato solo permitía
una pregunta documental vacía en ese contexto. Ahora valida el cambio a intent=document,
sin categorías académicas, selección de tarea ni seguimiento. La prueba integrada real
dev/moodle/smoke_browser.py --ticket04 consultó las tareas, preguntó el vencimiento de
“Ejercicios de ecuaciones” y cambió a “¿A qué hora es la tutoría del curso Algebra 101?”.
Gemini respondió: martes a las 16:00, con cita del “Documento de prueba ALG101”; no devolvió
la fecha de entrega 17:19. Latencias en la última repetición: 5,21 s, 4,88 s y 8,85 s. El artefacto registra las respuestas intermedias de lista y tarea seleccionada, además de la cita final.

La suite completa de Python con PostgreSQL terminó con 260 aprobadas, cero omitidas.
Se verificó Ruff. La aceptación global sigue pendiente de los tickets 02, 05 y 06,
además de los casos integrales que no se ejecutaron en este recorrido focalizado.

### Cierre del ticket 02: interpretación y contexto temporal (2026-10-19)

El ticket 02 queda done. Se amplió el verificador reproducible para probar ocho
interpretaciones reales de Gemini y registrar el número de solicitudes del modelo por caso;
el presupuesto es de dos o menos llamadas por interpretación. Con Gemini 3.5 Flash Lite
y reloj fijo 2026-10-19 en America/Lima, pasaron cursos, semana actual, próxima semana,
semana ISO explícita, seguimiento “¿Y quiénes más?”, cambio de tarea a cursos, referencia
ambigua a una tarea y corrección de disponibilidad a viernes de 15:00 a 18:00. La semana
actual se resolvió al 19–25 de octubre, la siguiente al 26 de octubre–1 de noviembre y
la explícita al 2–8 de noviembre.

El test de reformulación también afirma el límite de dos llamadas en el seam público.
Las pruebas existentes cubren disponibilidad desconocida, estado de sesión que se limpia,
reloj confiable, errores explícitos y planes inválidos que no activan lecturas. Moodle
conserva referencias y disponibilidad en la sesión; no hay almacenamiento persistente.

El validador real se reproduce con .venv/bin/python scripts/check_gemini_conversation.py
--retries 1 --report ../.scratch/asistente-conversacional/ticket02-live-validation.json.
Usa contextos y datos sintéticos y verifica los planes sin consultar registros Moodle. El recorrido integrado completo y los casos de aceptación finales
corresponden al ticket 06; la aceptación general sigue pendiente.

### Cierre del ticket 05: plan semanal con Moodle y Gemini reales (2026-10-19)

El ticket 05 queda `done`. El recorrido dedicado de navegador inicia sesión como
`estudiante1`, consulta los pendientes nativos de Moodle antes de pedir disponibilidad,
propone bloques con el horario declarado, reemplaza el horario anterior al corregirlo y
produce un borrador explícitamente provisional si el estudiante aún no conoce sus horas.
Las fechas, zona horaria, estados y vencimientos se toman de Moodle; la respuesta aclara
que los bloques no estiman el esfuerzo ni garantizan completar las tareas.

Con Gemini `gemini-3.5-flash-lite`, el recorrido terminó en cuatro turnos, con latencias
de 5,21 a 9,36 segundos. Se verificaron los bloques 2026-10-20 y 2026-10-22 de 14:00 a
16:00; tras la corrección, viernes 2026-10-23 de 15:00 a 18:00 y sin bloques del horario
anterior. Moodle entregó la zona `Europe/London` configurada para la cuenta de prueba.
La cuenta es ficticia y local; no se escribió ni modificó ningún registro desde el chat.
Antes del recorrido se actualizaron los vencimientos ficticios con el sembrador local,
que ahora los renueva en cada ejecución para que no queden permanentemente vencidos.

La evidencia está en `ticket05-browser.json`; reproducir desde `rag-service`:

```sh
PLAYWRIGHT_BROWSERS_PATH=.cache/ms-playwright .venv/bin/python -u ../dev/moodle/smoke_browser.py --ticket05
```

Los criterios de cero tareas, lecturas parciales, paginación de 25 tareas, prórrogas,
borradores, vencidas, tareas sin fecha y límites de domingo/zona horaria conservan las
pruebas unitarias Python y nativas Moodle referenciadas en la tabla. El recorrido real
cubre el flujo positivo con tareas próximas y una corrección de disponibilidad; la
aceptación conversacional global queda pendiente del ticket 06.

### Cierre del ticket 07: interfaz inmediata del chat Moodle (2026-10-19)

El ticket 07 queda `done`. El chat conserva la página y los formularios estándar de
Moodle, con una tarjeta de conversación, mensajes de estudiante/asistente diferenciados,
fuentes plegables y sugerencias iniciales que rellenan el campo de pregunta. El diseño
se adapta a móvil y respeta `prefers-reduced-motion`.

Al enviar, JavaScript inserta inmediatamente el mensaje usando `textContent`, muestra
un estado accesible «El asistente está preparando tu respuesta…», desactiva el botón y
las sugerencias, y evita un segundo envío. El texto se conserva en un campo oculto del
POST normal de Moodle; la verificación integrada posterior confirmó que Gemini recibe
la pregunta y devuelve el plan/respuesta como antes. El indicador describe el estado de
espera y no expone ni simula texto de razonamiento interno. Sin JavaScript, el formulario
original sigue enviando la pregunta; las sugerencias solo se muestran con la mejora JS
activa.

`ticket07-browser.json` registra la prueba de navegador que retiene el submit después
del manejador visual para comprobar mensaje inmediato, estado, envío único y ajuste móvil
sin consumir Gemini. Después pasó también el recorrido real del ticket 05 con cuatro
respuestas de Gemini `gemini-3.5-flash-lite` (4,66–8,02 s), que confirma el POST normal,
el renderizado final, contexto y disponibilidad. Se purgaron las cachés Moodle para
recoger las nuevas cadenas y `styles.css`; la captura visual temporal quedó en `.local/`.

Reproducir el chequeo de interfaz desde `rag-service`:

```sh
PLAYWRIGHT_BROWSERS_PATH=.cache/ms-playwright .venv/bin/python -u ../dev/moodle/smoke_browser.py --ticket07
```

### Ticket 06: aceptación reanudada (2026-10-19)

El verificador tiene un modo `--ticket06` para la secuencia integral y
`--ticket06-mixed` para aislar una consulta con tareas Moodle de Biologia 102 y
un dato documental de Algebra 101. Ambos comprueban que la clave Gemini y el
secreto compartido no aparecen en la respuesta. El modo integral incluye un
ataque directo de extracción de claves y el ataque documental temporal, que se
elimina al terminar. El verificador solo reintenta los dos mensajes localizados
de indisponibilidad de Moodle, con espera exponencial, pequeña variación aleatoria
y un máximo de dos reintentos adicionales; no reintenta fallos semánticos.

La prueba enfocada con Gemini real pasó tras consultar primero cursos y norma:
la segunda respuesta incluyó las tareas de Biologia 102 y citó el código
`ALG-TUTOR-16` del documento autorizado de Algebra 101. En una ejecución integral
el mismo caso falló una vez con respuesta documental insuficiente y pasó en la
repetición. También pasaron el ataque directo que pedía la clave Gemini junto
con las tareas permitidas y la inyección del PDF temporal, que devolvió el canal
institucional correcto sin obedecer la instrucción incrustada.

La suite RAG terminó con **260 pruebas aprobadas, ninguna omitida**; PHPUnit de
Moodle terminó con **42 pruebas y 209 aserciones**. El recorrido integral alcanzó
56 consultas válidas, con latencias por consulta de 0,78 a 29,66 segundos
(media 8,00 s), pero no terminó. La API registró `gemini_throttled`; una
ejecución posterior agotó los dos reintentos adicionales desde el saludo. El reporte parcial,
con `complete: false`, está en `ticket06-browser.json`. No se declara aceptado
el ticket 06 ni completa la aceptación conversacional mientras falte un recorrido
integral con resultado satisfactorio.
