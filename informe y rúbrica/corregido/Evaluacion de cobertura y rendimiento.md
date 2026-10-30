# Evaluación de cobertura y ampliación de rendimiento

Fecha: 29/10/2026. Alcance: asistente académico local Moodle–RAG, documentos PDF, cursos, docentes, tareas, notas, calendario, navegación y planificación. Se excluyen las pruebas exploratorias. Esta evaluación revisa código, pruebas, requisitos y evidencias guardadas; no representa una nueva ejecución del producto ni modifica sus resultados anteriores.

## Actualización posterior

La campaña ampliada ya se ejecutó hasta el bloqueo de cuota: ver [resultados medidos](rendimiento-ampliado-resultados.md). El análisis que sigue conserva la evaluación previa; sus escenarios propuestos no se presentan como ejecutados.

## Dictamen

**La cobertura existente es una base de aceptación, pero aún no es suficiente para afirmar que se evaluaron todos los riesgos relevantes del software.** Los 36 planes aprobados no equivalen a cobertura exhaustiva. Tampoco 295 pruebas Python y 53 de Moodle indican cuántas funciones o ramas están cubiertas: hay parametrización, pruebas de componentes, pruebas de integración y pruebas de proveedores alternativos.

Diez sesiones concurrentes son válidas para el objetivo anterior de diez sesiones; no demuestran capacidad para un campus, carga sostenida o recuperación después de saturación. Debe ampliarse la medición antes de afirmar una capacidad mayor. El objetivo de usuarios reales del campus todavía no está definido: los niveles propuestos abajo son una campaña de caracterización local, no una capacidad prometida ni un requisito externo universal.

Los cuatro contenedores del proyecto estaban detenidos durante esta revisión. El host consultado tiene cuatro CPU lógicas y aproximadamente 11 GiB de RAM. No se iniciaron servicios ni se consumieron llamadas a proveedores para esta evaluación.

## Qué demuestra realmente la evidencia actual

| Tipo | Cobertura encontrada | Evaluación |
|---|---|---|
| Unitarias | Reglas de conversación, fechas, planificación, extracción de PDF, validación de vectores, citas, errores y configuración; no solo las ocho mostradas en el resumen anterior. | Base amplia. Falta medir cobertura de ramas de módulos críticos y completar límites específicos de autenticación y saturación del transporte. |
| Integración | Base real aislada: ingreso/actualización/borrado, transacciones, concurrencia de ingesta, índices y permisos; contratos API y plugin Moodle. | Base sólida para las operaciones probadas. Falta acreditar recuperación del circuito completo ante caída/reinicio y cambios de acceso durante una conversación real. |
| Funcionales | Chat real, navegación, planificación, ambigüedad, información errónea, abstención y uso de escritorio/móvil. | Cobertura principal presente. Falta una matriz explícita de operaciones por perfil y una evaluación de IA independiente del conjunto usado para corregir el sistema. |
| Rendimiento | 100 solicitudes, diez sesiones, dos cuentas, cinco temas, ejecución final de 112,609 s; 100% en ≤10 s y p95 de 7,3972 s. | Insuficiente para capacidad superior, estabilidad prolongada, ráfagas y recuperación. |
| Seguridad | Firma, integridad del cuerpo, permisos, notas ajenas, sesión, datos sensibles, inyección de instrucciones y escape de HTML. | Controles importantes probados. Falta evidencia específica de CSRF en el controlador real, límites completos de la aserción y abuso concurrente. Una ausencia de prueba no demuestra una vulnerabilidad. |

Evidencia base: `.scratch/cumplimiento-rubrica-final/evidencias/{pytest.xml,phpunit.xml,funcionales.json,navegacion.json,interfaz.json,evaluacion-ia.json,carga.json}`. Los XML acreditan las ejecuciones guardadas; la inspección del código permite determinar qué comprueba cada prueba.

## Problemas de cobertura y trazabilidad de los 36 planes

1. **CP-011, CP-012 y CP-033 usan una sola carga.** Miden latencia, errores/concurrencia y muestras de disponibilidad de la misma ejecución. No equivalen a tres experimentos distintos de rendimiento.
2. **CP-015 agrupa suites mixtas.** Su etiqueta principal «Integración» no convierte todas las pruebas de pytest y PHPUnit en integración. La regresión debe seguir identificando los módulos y resultados que contiene.
3. **CP-035 verifica documentos y reproducibilidad.** Es válido para la entrega, pero no aumenta la cobertura funcional del aplicativo. Su clasificación en Funcionales se hizo dentro de los seis nombres solicitados y lleva una aclaración de celda.
4. **CP-009 describe varias variantes, pero su selector automático acredita solo la prueba de firma vencida/falsificada.** Otras variantes sí existen en `test_api_auth.py`; debe vincularse cada afirmación con sus resultados específicos.
5. **CP-021 describe varios rechazos de PDF, pero el selector acredita el límite de tamaño antes del parser.** Los módulos de documentos y extracción contienen otras verificaciones: deben enlazarse expresamente, incluidos límites de páginas/fragmentos cuando correspondan.
6. **CP-024 menciona DeepSeek, Gemini y recuperación de interfaz, pero el selector se limita a `test_deepseek`.** Deben adjuntarse las ejecuciones de Gemini y de la interfaz controlada para justificar el esperado completo.
7. **CP-025 resume limpieza y aislamiento, pero RF-09 también exige cierre y expiración.** Existen pruebas PHP específicas y recorridos históricos de navegador; deben figurar sus evidencias y fechas, sin asumir que se volvieron a ejecutar en el último recorrido funcional.
8. **CP-032 menciona pruebas Python y PHP, pero su selector usa `test_weekly_plan`.** Hace falta enlazar los resultados del contexto académico de Moodle sobre prórrogas y lectura parcial.

Estas son diferencias entre lo que el plan afirma y la evidencia que selecciona, además de las brechas nuevas. Corregirlas evita confundir «existe en el código», «se ejecutó en alguna ocasión» y «está acreditado en este resultado».

## Pruebas que deben completarse o hacerse explícitas

Prioridad alta: afecta autorización, integridad, aceptación de resultados o capacidad. Prioridad media: amplía robustez o alcance. «Pendiente» significa que no se localizó evidencia suficiente en la entrega revisada.

| ID de mejora | Tipo principal | Prioridad | Qué hay | Qué falta verificar | Resultado esperado |
|---|---|---|---|---|---|
| MEJ-01 | Unitarias | Alta | Rechazo de firma caducada/falsa y cuerpo alterado. | Matriz de límites: duración máxima de aserción, tolerancia de reloj, issuer/audience, formato/base64/JSON, longitud de token y número de cursos; antes/en/en exceso del límite. | Aceptar solo el contrato permitido; rechazo controlado sin consultar al RAG. Evidenciar cada variante. |
| MEJ-02 | Unitarias | Alta | Reutilización de conexiones y errores de transporte. | Agotamiento del pool, liberación de conexiones después de excepción y peticiones simultáneas con credenciales diferentes. | Sin mezcla de credenciales, fuga de conexiones ni espera ilimitada; error recuperable y medible. |
| MEJ-03 | Integración | Alta | Rollback y fallos simulados en componentes. | Inducir temporalmente indisponibilidad de API, base o proveedor en entorno de prueba y restaurar; observar el chat y la siguiente consulta. | Mensaje seguro, entrada recuperable, sin pérdida de índice ni duplicación de efectos; servicio operativo tras restauración. |
| MEJ-04 | Integración | Alta | Revalidación de accesos y grupos en pruebas PHP. | Retirar matrícula/permiso u ocultar actividad entre mensajes de una conversación real; comprobar también documentos de curso. | La siguiente consulta y sus destinos no conservan accesos retirados ni revelan datos por contexto anterior. |
| MEJ-05 | Funcionales | Alta | Recorridos con estudiante y docente; lectores probados por separado. | Matriz explícita estudiante/docente/administrador autorizado × cursos/docentes/tareas/notas/calendario/plan; incluir vacío, datos parciales y ambigüedad. | Datos exactos del perfil y fuente correcta; ningún acceso adicional por declarar un rol en el mensaje. Aprovechar las pruebas existentes antes de duplicarlas. |
| MEJ-06 | Funcionales | Alta | 36 positivas y cinco abstenciones, con comparación automatizada. | Conjunto nuevo reservado: paráfrasis, consultas compuestas, contradicciones, cambios de documentos, datos académicos modificados y preguntas sin respuesta; revisión de hechos/fuentes por una persona. | Medir aciertos, abstenciones y errores por categoría; fijar el criterio antes de ejecutar. No ajustar los ejemplos reservados después de ver los fallos. |
| MEJ-07 | Funcionales | Media | Chromium en escritorio/móvil y teclado básico. | Foco, etiquetas, lectura con tecnología de asistencia, zoom y recuperación de navegación; otro navegador solo si se incorpora al alcance declarado. | Interacción completa sin ratón, errores comprensibles y lectura sin pérdida de contenido. No afirmar compatibilidad universal. |
| MEJ-08 | Seguridad | Alta | `require_sesskey()` en `index.php`. | POST real sin token de sesión y con token incorrecto para enviar y limpiar conversación. | Rechazo sin invocar IA ni modificar la conversación. El control existe; falta evidenciar el rechazo en ese recorrido. |
| MEJ-09 | Seguridad | Alta | Escape de texto en PHPUnit y prueba de navegador de la página demo. | Cadenas HTML/JavaScript maliciosas en entrada, respuesta, fuente y destino del chat Moodle completo. | Ningún script ejecutado ni enlace peligroso utilizable; contenido mostrado como texto seguro. No confundir la página demo con el plugin. |
| MEJ-10 | Seguridad | Alta | Firma con vigencia limitada y rechazo de identidad alterada. | Repetición del mismo mensaje firmado dentro de su vigencia, duplicación simultánea y abuso por sesión; definir si el contrato exige deduplicación y cómo se limita consumo. | Comportamiento definido, medido y sin exposición; si se requiere bloqueo, implementarlo y probarlo. No afirmar protección anti-replay a partir de una firma solamente. |
| MEJ-11 | Seguridad | Media | Revisión de secretos configurados y puertos locales. | Revisar dependencias efectivamente instaladas y sus avisos aplicables; verificar permisos/configuración de la ruta demo y mensajes de error en el despliegue evaluado. | Registrar hallazgos reales con alcance y resolución; no aprobar por el solo hecho de ejecutar un escáner. |
| MEJ-12 | Rendimiento | Alta | Una carga breve de diez sesiones. | Carga escalonada, sostenida, picos, recuperación, cuentas distintas, monitoreo y validación semántica descritos abajo. | Determinar la mayor carga medida que cumple el objetivo y reportar dónde deja de cumplirlo. |

Complemento transversal: obtener cobertura de ramas en módulos críticos Python y una matriz de requisitos/controles PHP. El porcentaje de líneas es información auxiliar; no reemplaza los comportamientos anteriores. No se fija un porcentaje arbitrario como prueba de corrección.

## Cómo ampliar rendimiento

### Primero corregir la medición

En `dev/validation/load_chat.py`:

- `--users` permite únicamente 1–10. Cambiar solo ese máximo no basta para una campaña de capacidad.
- `ask()` considera éxito la ausencia de error visible y la existencia de una respuesta no vacía. Debe validar también hechos y permisos mínimos según la pregunta: 11 con fuente para nota mínima, cursos propios sin restringidos, destino válido para calendario, etc. Una respuesta rápida incorrecta debe contar como fallo.
- Se restablece la conversación antes de cada ronda; faltan cadenas de seguimiento bajo carga.
- Se reutilizan dos cuentas; para hablar de estudiantes distintos se necesitan cuentas distintas, cada una con su contexto. Cookies distintas no equivalen a diez identidades.
- Las cinco consultas no incluyen notas, tareas detalladas, planificación o peticiones mixtas. Incorporarlas con una distribución declarada que conserve suficientes consultas documentales.
- Registrar CPU, RAM, swap, contenedores, conexiones a base/proveedores y errores 429/5xx/timeouts. El cliente de proveedores tiene un pool de 20 conexiones y espera de pool de hasta tres segundos; es una posible restricción que debe medirse, no una equivalencia con veinte usuarios.
- El generador y el sistema comparten equipo. A cargas altas, Chromium puede saturar el propio generador. Separar su consumo; si se usa un segundo generador, conservar la restricción local o definir explícitamente el nuevo entorno. Un ensayo HTTP de componentes debe etiquetarse aparte y no sustituir la latencia del chat completo.

### Campaña propuesta, todavía no ejecutada

| Escenario | Carga y duración propuesta | Qué responde |
|---|---|---|
| Línea base | 1 y 10 sesiones; calentamiento aparte; al menos 100 consultas medidas por nivel. | ¿La versión actual reproduce la referencia anterior antes de aumentar carga? |
| Escalonada | 10 → 25 → 50 → 75 → 100 sesiones; sostener cada nivel al menos cinco minutos y reunir al menos 500 solicitudes por nivel. Avanzar solo si el generador y los servicios se mantienen estables. | ¿Hasta qué nivel cumple el objetivo? Los 100 son un máximo inicial de exploración de capacidad, no una garantía de soporte. |
| Sostenida | Mayor nivel estable de la escalonada durante 60 minutos; actividad con pausas declaradas y seguimientos. | ¿Aumenta la latencia o la memoria con el tiempo? ¿Se agotan conexiones o cuotas? Es una prueba de una hora, no de operación continua indefinida. |
| Pico | Partir de diez, subir rápidamente al mayor nivel estable durante un minuto y volver a diez; observar recuperación durante cinco minutos. | ¿El sistema absorbe una subida brusca y recupera el servicio normal? |
| Estrés y recuperación | Incrementos de 25 sesiones más allá del nivel estable, hasta el primer incumplimiento sostenido o límite del entorno; reducir de nuevo a diez. | ¿Dónde se degrada y cómo se recupera? El incumplimiento documenta el límite, no debe ocultarse como resultado aprobado. |
| Volumen y actividad concurrente | Corpus y matrículas con volumen documentado mayor al preparado; lectura mientras se actualiza un documento; sin usar datos personales reales. | ¿La capacidad depende de un corpus pequeño? ¿La actualización conserva coherencia bajo consultas? |

Las duraciones y cantidades son una propuesta concreta para este proyecto, no cifras prescritas por una norma. Se debe estimar consumo de tokens/cuotas antes de ejecutar la campaña completa. La prueba de estrés debe limitarse a los componentes propios; no se busca saturar los servicios externos de IA.

Mantener en cada nivel normal el criterio anterior: **al menos 95% de todas las solicitudes correctas en ≤10 s y cero errores de aplicación/transporte**. Contar como fallo las respuestas incorrectas y no eliminar timeouts. Registrar p50, p95, p99, máximo, solicitudes/s, corrección, errores y consumo de recursos por etapa. Con pocas muestras, especialmente en p99, declarar su limitada precisión; repetir el nivel candidato de aceptación para comprobar variación entre ejecuciones.

Criterios de parada propuestos: detener incrementos ante reinicios/OOM, pérdida de disponibilidad durante 30 s o más de 5% de errores en una ventana de un minuto; conservar muestras y evaluar recuperación. No continuar saturando el equipo para alcanzar el número 100. La recuperación propuesta exige cinco minutos de carga base cumpliendo otra vez el criterio normal, sin mezcla de sesiones ni pérdida de datos.

Distinguir tres magnitudes en el informe: cuentas con sesión abierta, usuarios activos y consultas simultáneas. El resultado debe expresarse así: «se midieron N sesiones bajo esta mezcla, duración y equipo; el nivel N cumplió/no cumplió», sin extrapolar a toda la universidad.

## Orden de cierre

1. Corregir trazabilidad de los planes que afirman más variantes de las que seleccionan sus evidencias.
2. Completar controles críticos de autenticación, CSRF, permisos y recuperación; aprovechar las pruebas existentes de sesión, HTML y roles.
3. Fortalecer el arnés de carga y reunir evidencia escalonada, sostenida y de recuperación con el criterio ya definido.
4. Completar la matriz funcional por perfiles y la evaluación independiente de IA.
5. Incorporar nuevos planes identificados y resultados reales; conservar pendientes/fallos como tales. No sobrescribir la ejecución histórica ni aumentar la cantidad de usuarios en el informe sin medirla.

## Referencias consultadas

- Grafana, [guías de pruebas de carga](https://grafana.com/docs/k6/latest/testing-guides/) y [carga de sitios web](https://grafana.com/docs/k6/latest/testing-guides/load-testing-websites/): distinguir objetivo, tipo de carga y alcance frontend/backend.
- OWASP, [Web Security Testing Guide](https://wstg.owasp.org/stable/4-Web_Application_Security_Testing/): referencia para revisar autenticación, autorización, sesión y entradas. Su uso guía la revisión; no equivale a una certificación OWASP.

Referencias locales: `dev/validation/load_chat.py`, `dev/validation/report_content.py`, `dev/validation/build_deliverables.py`, `rag-service/tests/`, `rag-service/src/rag_service/moodle_auth.py`, `rag-service/src/rag_service/provider_http.py`, `moodle/public/local/acadassistant/tests/`, `moodle/public/local/acadassistant/index.php` y `.scratch/cumplimiento-rubrica-final/spec.md`.
