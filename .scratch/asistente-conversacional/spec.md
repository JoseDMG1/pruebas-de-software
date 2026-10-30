# Asistente conversacional de vida universitaria

Status: approved

## Problema

El chat actual trata saludos y entradas no reconocidas como búsquedas documentales;
respuestas basadas en listas y reglas no comprenden suficientemente reformulaciones,
confirmaciones ni solicitudes de ayuda personalizada. Los datos y permisos disponibles
son útiles, pero falta una coordinación conversacional que elija cuándo consultarlos.

## Objetivo

Conversar naturalmente dentro de la vida universitaria, entender la intención y el
contexto de la sesión, consultar fuentes autorizadas cuando corresponda y responder
con información y orientación pertinentes. Cubrir saludos, confirmaciones y planificación
personal mediante un comportamiento generalizable, no una lista de frases exactas.

El diseño conserva [ADR-0001](../../docs/adr/0001-moodle-autoriza-datos-academicos.md)
y el lenguaje de [GLOSSARY.md](../../GLOSSARY.md).

## Alcance acordado

- Información institucional respaldada por documentos pertinentes.
- Orientación de uso de Moodle basada en guías verificadas para el portal.
- Consultas académicas personales autorizadas: cursos, docentes visibles, tareas,
  estados, calificaciones visibles y calendario; conservar las fronteras ya aprobadas.
- Organización del estudio, incluido un plan semanal basado en tareas pendientes reales.
- Saludos, cortesía, despedidas y preguntas sociales breves solo cuando esa sea la intención.

Fuera de esta etapa: tutoría de contenidos, resolución de ejercicios, conversación o
entretenimiento general, pagos personales, escrituras en Moodle, historial persistente
y metas de carga. El plan es una sugerencia; no modifica entregas, fechas ni calendarios.

## Reglas de conversación

1. «Hola, ¿cómo estás?» responde cordialmente sin recuperar documentos ni datos personales.
   Explicar las capacidades del asistente tampoco necesita una búsqueda documental.
2. Una consulta de ayuda selecciona las fuentes según lo que necesita: Moodle para datos
   dinámicos, RAG para documentación pertinente, ambos cuando corresponda. No exigir
   documentación para confirmar un dato que ya procede de Moodle.
3. Entender variantes, reformulaciones, referencias y cambios de tema. Mantener contexto
   temporal suficiente para la tarea actual sin arrastrar filtros de temas independientes.
4. Responder directamente a confirmaciones y negaciones según datos comprobados; no
   sustituir la respuesta por repetir toda la lista ni incluir calendario/documentos ajenos.
   Visibilidad no prueba ausencia de personas asignadas; homónimos no son una sola identidad.
5. En mensajes mixtos, atender únicamente las partes permitidas. Un saludo solicitado puede
   acompañar la respuesta académica; no introducir charla social en consultas de ayuda.
6. Rechazar brevemente solicitudes ajenas al ámbito y orientar hacia capacidades permitidas,
   sin desarrollar contenido del tema rechazado. Mencionar «universidad» o un curso no basta
   para convertir una solicitud ajena en orientación universitaria permitida.
7. Si falta evidencia para una norma o una instrucción del portal, explicar exactamente el
   límite; no inventar reglas, pasos, pantallas o respuestas tomadas de ejemplos del prompt.
8. Distinguir resultado vacío conocido, lectura parcial, error y falta de fuente. La evidencia
   de Moodle y las citas documentales mantienen procedencias separadas.

## Plan semanal académico

- Leer en vivo tareas pendientes autorizadas, incluidos borradores, con cursos y vencimientos
  efectivos, incluyendo excepciones y prórrogas de Moodle.
- Recuperar páginas necesarias y comprobar tanto `has_more` como `complete`; no presentar una
  página de 20 tareas como el conjunto completo. Mantener revalidación y ausencia de duplicados.
- Consultar tareas antes de preguntar por disponibilidad. Si el usuario ya la indicó, usarla;
  de lo contrario, pedirla brevemente. No convertir duración de eventos en esfuerzo de tareas.
- Si no puede precisar disponibilidad, ofrecer un borrador por vencimientos con supuestos
  explícitos. Distribuir trabajo en los espacios disponibles no garantiza completar una tarea.
- Mostrar fechas del intervalo. Por defecto: desde hoy hasta el domingo actual, en la zona
  horaria de Moodle. Una semana indicada explícitamente reemplaza ese intervalo; si es ambigua,
  pedir aclaración. Fecha actual y zona horaria provienen del servidor, no de afirmaciones del modelo.
- Separar vencidas, próximas y sin fecha. Preguntar prioridad cuando faltan fechas y considerar
  entregas futuras para anticipar trabajo. No afirmar aceptación de entregas tardías ni prórrogas
  sin evidencia. Con cero pendientes comprobados, comunicarlo sin fabricar tareas.
- Si una lectura falla o alcanza límites, explicar qué falta y pedir acotar o reintentar;
  cualquier propuesta basada en datos incompletos se identifica como parcial.
- La disponibilidad declarada y los datos necesarios para el plan permanecen solo en la sesión
  actual, se usan cuando son pertinentes y se borran con nueva conversación, logout o expiración.

## Diseño propuesto

Separar interpretación, autorización/lectura y respuesta. El modelo interpreta lenguaje
natural y propone un plan estructurado dentro de operaciones permitidas. Moodle valida
ese plan y ejecuta únicamente lecturas nativas que el usuario puede realizar. RAG recupera
solo documentos autorizados. La respuesta se redacta de forma natural a partir de esos
resultados, conservando hechos verificables, citas y advertencias de incompletitud.

La interpretación debe recibir contexto temporal pertinente antes de decidir si un mensaje
es seguimiento; el filtro actual por frases no puede impedir ese acceso. Mantener estado
semántico acotado para referencias y disponibilidad, sin historial persistente. Un plan
inválido o ambiguo produce aclaración o error explícito, no lecturas más amplias por defecto.

Usar DeepSeek V4.1 Flash mediante Chat Completions (`deepseek-flash`) para interpretar consultas
y redactar respuestas. Usar Gemini Embeddings (`gemini-embedding-001`) para consultas e ingesta,
con una dimensión fija de 768 y los tipos de tarea de recuperación correspondientes; DeepSeek
no ofrece un endpoint de embeddings. No usar otro modelo de generación ni fallback. Validar JSON
con los contratos Pydantic del servidor y no asumir function calling para autorizar lecturas.
Las claves DeepSeek y Gemini se configuran únicamente en el servidor RAG y nunca se envían a
Moodle, al navegador, como contenido del modelo ni a los logs. Mantener acotados los tiempos de
espera, tamaños y llamadas. Conservar la firma del cuerpo, identidad y alcance verificados,
así como compatibilidad de los contratos de consulta existentes.

Reintentar únicamente fallos transitorios con espera exponencial y una pequeña variación
aleatoria: por defecto dos reintentos adicionales, configurables entre cero y tres mediante
`DEEPSEEK_MAX_RETRIES` para generación y `GEMINI_MAX_RETRIES` para embeddings. Un reintento
conserva el proveedor/modelo seleccionado; errores de petición o credenciales no se reintentan.
Cada intento respeta el timeout configurado.

Los espacios vectoriales de Ollama/Bedrock no son compatibles con Gemini. La migración de
base debe admitir embeddings Gemini sin mezclar espacios; un comando de migración recalcula
los embeddings desde los fragmentos almacenados antes de habilitar búsquedas sobre el corpus.
La ingesta debe seguir siendo transaccional por documento y preservar la versión anterior si
Gemini falla.

## Límites y resistencia a abuso

- El modelo no autoriza acceso, asigna roles ni ejecuta código, SQL, comandos o URLs arbitrarias.
- Herramientas enumeradas con argumentos validados; identidad y permisos calculados por Moodle.
  Un identificador o un cargo declarados en el mensaje no amplían acceso.
- Mensajes, documentos y resultados son contenido no confiable para instrucciones; no pueden
  sustituir las políticas ni habilitar operaciones adicionales.
- Mantener límites de entrada, contexto y consultas; evitar bucles de herramientas sin límite.
- Verificar también la salida: ámbito, relación con la pregunta, hechos contra resultados y
  procedencia. Si una respuesta no puede validarse, aclarar o informar el fallo; no publicarla
  como un dato confirmado.
- Probar ataques directos, instrucciones dentro de documentos, suplantación de rol, extracción
  de secretos y mezclas de solicitudes válidas con otras prohibidas. Estas pruebas y controles
  no representan una garantía absoluta contra toda inyección o abuso posible.

## Guías de uso del portal

Incorporar un conjunto acotado de guías verificadas en el Moodle realmente usado para las
pruebas, con versión y alcance indicados. No presentar una guía genérica como una instrucción
verificada de este portal. Registrar las preguntas cubiertas y los límites; si faltan pasos
para una consulta, conservar el comportamiento de evidencia insuficiente pertinente.

## Recorridos de aceptación

- Saludo, agradecimiento y despedida, incluidos mensajes con saludo y consulta académica.
- Secuencia literal de docentes del usuario y confirmación de Carla, sin fechas, PDF ni Diseño 204.
- Variantes no incluidas literalmente en ejemplos, correcciones, cambio de tema y referencias ambiguas.
- Ayuda dentro/fuera del ámbito: guía Moodle respaldada, procedimiento sin evidencia, tutoría excluida.
- Organizar semana: tareas reales primero, disponibilidad después, plan y modificación con nueva
  preferencia; cero tareas, vencidas, sin fecha, prórrogas, más de 20 pendientes y lectura fallida.
- Intervalo explícito y por defecto, domingo, zona horaria y rechazo de fechas inventadas.
- Diferencias de permisos estudiante/docente/autoridad, homónimos y revalidación durante continuación.
- Datos locales del prompt no aparecen como hechos; las citas solo respaldan documentos usados.
- Ataques de instrucción directos y documentales; mensajes mixtos atienden la parte autorizada.
- Proveedor DeepSeek para interpretación y respuestas, Gemini para embeddings; claves ausentes, timeout,
  límite de cuota, respuesta JSON inválida y reindexación sin mezcla de espacios.
- Nueva conversación, logout y expiración borran referencias, disponibilidad y cursores.
- Recorrido real Moodle + DeepSeek con comprobaciones semánticas, además de pruebas de contratos.

## Verificación y despliegue

Usar TDD en los seams públicos ya usados: cliente DeepSeek, proveedor de embeddings, servicios
Moodle con usuarios y capacidades nativas, endpoints protegidos RAG, store temporal y
navegador real. Conservar las suites existentes y ampliar pruebas que detecten respuestas
incorrectas, no solo transporte HTTP exitoso. Probar contratos JSON, errores del proveedor,
ausencia de fallback local y reindexación completa en un entorno de prueba.

Aplicar sobre el entorno local Moodle 5.3dev de prueba, sin afirmar compatibilidad con una
versión desplegada aún no confirmada. Registrar latencia observada del flujo completo y
errores; las metas de carga continúan aplazadas. No publicar ni desplegar fuera del entorno local.

## Aprobación

El usuario confirmó explícitamente el entendimiento compartido y aprobó el alcance
conjunto de esta spec y los seis tickets. Código implementado en el entorno local;
la aceptación final sigue pendiente. Véase [verification.md](verification.md).

## Navegación autorizada (2026-10-22)

El asistente interpreta solicitudes para abrir cursos, tareas, informes de notas y calendario.
Moodle construye los destinos desde registros autorizados y capacidades efectivas. Un docente
puede recibir enlaces de calificación; un alumno recibe su informe personal. Los enlaces no
ejecutan modificaciones automáticamente.

Para el vencimiento más próximo, se consideran las fechas futuras efectivas de las tareas
pendientes, incluidas prórrogas. Se recorren las páginas necesarias y se devuelven todos los
empates. Si la lectura alcanza un límite, se pide acotar el curso sin afirmar un mínimo global.
Los destinos se validan y escapan antes de conservarse y mostrarse en la conversación.

## Presentación de respuestas (2026-10-22)

Las respuestas académicas con varias entidades se muestran como encabezados y listas,
con el nombre de cada elemento separado de sus detalles y fechas en español. Moodle
escapa el texto antes de generar el marcado de presentación; solo los destinos autorizados
por Moodle se representan como enlaces. Los detalles de los enlaces aparecen una sola vez.
Las conversaciones previas conservan el mismo formato al volver a abrir el chat.
