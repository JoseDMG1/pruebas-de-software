# Verificación de respuestas académicas confiables

Comparación de revisión autorizada: `1cf28883be6e550f7c1d3a3805afbc7f5a45b1c1`.
Implementación revisada hasta `2852bb494` en `main`.

## Pruebas automatizadas

- Moodle 5.3dev, PHP 8.3 y PostgreSQL 17: **30 tests, 112 assertions**, todos pasan.
  Ejecutar `docker compose -f compose.moodle.yaml exec -T moodle vendor/bin/phpunit --testsuite local_acadassistant_testsuite`.
- RAG: **156 pruebas**, todas pasan, incluidas integraciones PostgreSQL; sin omisiones.
  Ejecutar `TEST_DATABASE_URL=postgresql://rag:rag_local_dev@127.0.0.1:55432/rag_sprint2_tests rag-service/.venv/bin/python -m pytest rag-service/tests -q --require-complete`.
- Ruff, sintaxis PHP del plugin, sintaxis Bash de arranque y `git diff --check`: pasan.
- RAG desplegado localmente devuelve `{"status":"ok","database":"ok"}`.

Las pruebas Moodle cubren matrícula frente a acceso global y responsabilidad docente,
visibilidad nativa de docentes y grupos, pendientes frente a entregadas, filtros de curso,
seguimientos y cambio de tema, prórrogas individuales leídas en vivo, paginación con
revalidación y borrado del contexto por logout, expiración y cambio de identidad.
Las pruebas RAG cubren contrato protegido y alcance documental firmado, composición
académica independiente del modelo, distinción entre vacío/error/parcial, evidencias
separadas, discrepancias de calendario y conservación de la parte académica ante
fallos documentales.

## Recorrido real

`dev/moodle/smoke_browser.py` finalizó con código **0** utilizando Chromium,
el sitio Moodle real, PostgreSQL y Ollama `qwen2.5:3b` / `qwen3-embedding:0.6b`.
El reporte final está en `.local/moodle-browser-report.json` y la salida en
`.local/respuestas-browser-final.log`; ambos y las capturas están excluidos de Git.

Comprobaciones realizadas:

- Anónimo sin chat; enlace global para cuentas personales; secreto ausente del HTML.
- Secuencia reportada tareas → cuotas → profesores → cursos → cursos y variantes.
- Seguimientos encadenados, aclaración de tarea ambigua, selección de nombre y cambio de tema.
- Respuestas mixtas: cursos y cuotas; cursos y reglamento; tareas BIO102 y documento ALG101,
  con alcance independiente y cita del documento pertinente.
- Nota mínima institucional 11; estudiante1 sin código ni fuente RES103;
  estudiante2 recibe ORQUIDEA-73 **desde el PDF RES103**, no desde la tarea homónima.
- Estudiante2 sin pendientes BIO102 pero con su entrega presentada.
- Docente ve nota 85 de Luis; autoridad distingue matrícula propia vacía de acceso general.
- Nueva conversación, logout y timeout nativo eliminan el contexto.
- Lista de 22 cursos: página 01–20 parcial, continuación 21–22 sin duplicados,
  y cursor eliminado por nueva conversación.

El login del harness espera la inicialización AJAX del formulario para evitar
rellenar un campo de contraseña que Moodle reemplaza durante la carga.

## Standards

Revisión por agente independiente: **sin hallazgos pendientes**. Se eliminó una rama
duplicada de resolución de cursos. Vocabulario, autorización Moodle, credenciales
servidor a servidor y seguimiento de issues respetan las convenciones documentadas.

## Spec

Revisión por agente independiente: **sin hallazgos pendientes de código**.
Se corrigieron dos hallazgos con regresiones RED → GREEN: conservar la tarea seleccionada
en seguimientos encadenados y respetar las prórrogas individuales de Moodle.
Las abstenciones documentales sobre RES103 y ALG101 se reprodujeron con el modelo real pese a recuperar
los fragmentos correctos. Las instrucciones ahora explican que los fragmentos ya están
filtrados por acceso, con un ejemplo distinto del corpus de prueba; la comprobación
directa respondió ORQUIDEA-73 citando el documento autorizado. El recorrido completo
desde Moodle también pasó con estas correcciones.

## Límites

Datos y usuarios de prueba ficticios. Pagos personales y escritura en Moodle están
fuera de alcance. La interpretación cubre operaciones académicas soportadas y sus
variantes; no garantiza comprender cualquier expresión libre. Las respuestas
documentales siguen dependiendo del modelo local. Una lista limitada se anuncia
como parcial. La validación de rendimiento/carga continúa aplazada al Sprint 3.
El checkout de prueba es Moodle 5.3dev; no se certificó otra versión desplegada.

Resultado de revisión: Standards 0 hallazgos pendientes; Spec 0 hallazgos pendientes.


## Corrección de confirmaciones sobre docentes

Implementación revisada hasta `871d857ad`, sobre la comparación autorizada `1cf28883b`.
El reporte anterior no cubría la secuencia nueva que reportó el usuario.

Se reprodujo con el proveedor público la mezcla indebida de docentes y calendario,
y con el endpoint protegido la falta de confirmación directa. «Este ciclo» se trata
como contexto de la consulta personal sobre docentes, no como solicitud automática
de fechas o documentos. Preguntas explícitas sobre inicio del ciclo mantienen sus fuentes.
«Me refería» mantiene el contexto de la reformulación. La petición de exclusividad
produce una confirmación desde los docentes visibles de Moodle, con límites de
completitud y visibilidad, sin invocar generación documental.

La revisión detectó dos casos adicionales, corregidos con regresiones: sinónimos
«profes» / «quiénes me enseñan» y docentes homónimos. La identidad Moodle viaja solo
entre servidores para contar personas y paginar; no se muestra en la respuesta.
Un mismo docente en dos cursos cuenta una sola vez; dos personas con el mismo nombre
no producen una confirmación falsa. Sin identidad comprobable, la respuesta no afirma unicidad.

Pruebas actuales: **31 tests Moodle, 139 assertions; 164 pruebas RAG**, todos pasan.
Ruff, sintaxis PHP y `git diff --check` pasan. Revisión: Standards 0 hallazgos
pendientes; Spec 0 hallazgos pendientes de código.

El recorrido completo de navegador terminó con código **0**, con las cinco variantes
docentes y la confirmación literal del usuario. El reporte incluye
`teacher_confirmation_sequence`; la salida está en `.local/teacher-confirmation-browser.log`.
No apareció calendario, contenido documental ni Diseño 204 en esos turnos.
También pasaron las comprobaciones anteriores de documentos, permisos, tareas,
logout, expiración y continuación.

Respuesta real:

> Sí, Carla Docente es la única docente visible en los cursos consultados de Moodle. No puedo asegurar que no haya otros docentes asignados: no tengo nombres visibles en Algebra 101.
