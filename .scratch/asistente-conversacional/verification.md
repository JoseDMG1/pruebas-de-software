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
| 02 | Contexto antes de interpretar, referencias, cambios de tema y estado temporal; horarios declarados separados de intención | `test_conversation.py`, `conversation_store_test.php`; ajustes de horario conservan el curso activo |
| 03 | Lecturas con capacidades reales, matrícula, grupos, entregas, estados y prórrogas; guía local verificada | `academic_context_provider_test.php`, `conversation_test.php`, `docs/portal/moodle-5.3dev-guia.md` |
| 04 | Confirmación directa con identidades visibles, homónimos, citas documentales independientes, discrepancias de calendario y prioridad oficial | `test_conversation.py`, `test_document_evidence.py`, suites académicas existentes |
| 05 | Pendientes antes de disponibilidad, agregación de 25 tareas, intervalos, domingo, zona, vencidas/borradores/sin fecha, datos parciales y cero tareas | `conversation_test.php`, `test_weekly_plan.py`, pruebas nativas de prórrogas |
| 06 | Recorridos semánticos reales, acceso por cuenta, inyección directa/documental y borrado de sesión | `dev/moodle/smoke_browser.py`, suites de contratos/sesión y reporte local |

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

Verificación automatizada local: Ruff sin hallazgos y **235 pruebas aprobadas**, con **12
pruebas de PostgreSQL omitidas** por falta de entorno de integración. No se hizo una llamada
real ni reindexación: `GEMINI_API_KEY` no está configurada y no hay servicios Docker activos.
Las pruebas cubren errores de cuota, timeout y respuesta JSON inválida. La reindexación completa
y la preservación del índice anterior ante fallo aún requieren la base PostgreSQL de prueba.
Por ello, el recorrido Moodle + Gemini y la aceptación conversacional siguen pendientes; los
resultados con Ollama descritos arriba son históricos y no validan este proveedor.
