# Asistente académico global de Moodle — Sprint 2

## Objetivo

Ofrecer un chat inteligente desde la navegación principal de Moodle. Una persona con una cuenta personal autenticada puede hacer preguntas en lenguaje natural y recibir respuestas sustentadas por documentos institucionales o por datos académicos de Moodle que tenga permiso efectivo para consultar.

El asistente abarca todos los cursos autorizados de la persona sin exigir que entre a un curso. Puede acotar una consulta al curso que la persona mencione.

## Usuarios y autorización

- Solo pueden usar el asistente personas con una cuenta personal autenticada de Moodle. Se excluyen invitados.
- Moodle es la autoridad para la identidad y los permisos efectivos. Estos se evalúan en su contexto correspondiente; el nombre de un rol o cargo por sí solo no concede acceso.
- Una persona puede consultar sus propios datos académicos visibles. Docentes pueden consultar datos de estudiantes solo cuando sus capacidades en ese curso se lo permiten. Personal de alto mando puede acceder a datos de alcance general solo si Moodle les concede permisos efectivos para ello.
- Los documentos institucionales comunes están disponibles para cuentas personales autenticadas. Los documentos asociados a un curso solo se incluyen para participantes a quienes Moodle permite acceder a ese curso.
- El plugin Moodle llama al RAG desde el servidor. La credencial nunca se envía al navegador. La petición incluye una aserción firmada de corta duración; RAG la valida y aplica el filtro de documentos antes de recuperar fragmentos o generar la respuesta.

## Fuentes en Sprint 2

### Documentos institucionales

Cada documento debe declarar su alcance al cargarse: institucional común o asociado a uno o más cursos Moodle. Un documento sin clasificación explícita no participa en respuestas. El alcance de un documento de curso no reemplaza la comprobación de permisos de Moodle.

### Datos académicos de Moodle

Se consultan en vivo y en modo de solo lectura, según la pregunta y las capacidades efectivas de la persona. El primer alcance incluye los datos académicos que Moodle ya presenta a esa persona: cursos, actividades y fechas relevantes, estados de entrega, calificaciones visibles y eventos del calendario. Para preguntas sobre otros participantes, el plugin debe comprobar los permisos aplicables en el curso o contexto antes de obtener esos datos.

El plugin proporciona al RAG solo el contexto académico necesario para responder esa pregunta. El asistente no cambia entregas, calificaciones, matrículas ni otros datos de Moodle.

### Calendario académico

El asistente puede usar eventos visibles en el calendario Moodle y fechas publicadas en documentos institucionales oficiales. Si las fuentes muestran fechas distintas, identifica las dos, señala la discrepancia y trata el documento institucional oficial como referencia.

## Experiencia de conversación

- La página del asistente está disponible desde la navegación global del sitio, sin necesidad de abrir un curso.
- Una pregunta puede consultar todos los cursos a los que la persona tiene acceso; la persona puede acotar la consulta a un curso.
- Mientras una conversación está activa, sus mensajes previos pueden aportar contexto a preguntas de seguimiento.
- “Nueva conversación” elimina el contexto anterior. Cerrar o dejar expirar la sesión Moodle también termina y elimina el contexto temporal.
- No se guarda una lista de conversaciones ni existe historial recuperable entre sesiones.
- Si una pregunta no tiene evidencia en una fuente disponible o el acceso no está autorizado, el asistente lo comunica sin inventar datos ni revelar información restringida.

## Fuera de alcance

- Pagos, cuotas, saldos, precios de matrícula y vencimientos personales; no se integra un sistema financiero, de pagos ni de matrícula.
- Historial persistente de conversaciones.
- Metas o certificaciones de carga; se tratarán en Sprint 3.
- Acciones que modifiquen datos de Moodle.
- Acceso a datos personales por el cargo declarado, sin permiso efectivo de Moodle.

## Plataforma y restricciones actuales

El objetivo provisional es el checkout incluido en `moodle/`, Moodle 5.3dev, rama 503, build 20260911, alfa. La versión realmente desplegada no está confirmada y debe verificarse antes de desplegar el plugin. El RAG de `rag-service/` actualmente no autentica consultas, no recibe identidad o contexto de curso, recupera entre todos los documentos y no conserva contexto de conversación; estos son cambios requeridos por esta spec.

## Criterios de aceptación

1. Una persona autenticada encuentra el asistente desde la navegación global. Un invitado o una petición sin sesión Moodle válida no puede usarlo.
2. Una persona puede preguntar por datos académicos a través de varios cursos accesibles sin seleccionar uno primero; al limitar la pregunta a un curso, solo se usan datos y documentos permitidos para ese curso.
3. Los datos de Moodle se consultan en vivo, en modo de solo lectura, y solo se entregan al modelo después de las comprobaciones de permiso correspondientes.
4. Una persona estudiante no puede obtener entregas o calificaciones de otra persona. Un docente solo puede obtener datos de participantes en contextos donde Moodle le concede las capacidades necesarias. Los permisos de alto mando también se comprueban en Moodle; el cargo no sustituye esa comprobación.
5. Un documento institucional común puede fundamentar respuestas de cualquier cuenta personal autenticada. Un documento de curso no llega a recuperación ni al prompt si el usuario no tiene acceso autorizado al curso. Documentos sin alcance no aparecen en respuestas.
6. El API RAG rechaza credenciales o aserciones ausentes, inválidas o vencidas. Alterar en el cliente el identificador de usuario o curso no amplía acceso. Ninguna credencial del RAG aparece en el navegador.
7. Ante fechas académicas contradictorias, la respuesta identifica sus fuentes, reporta la discrepancia y presenta el documento institucional oficial como referencia.
8. Una pregunta fuera de alcance o sin información suficiente recibe una explicación breve y no una respuesta inventada.
9. Una pregunta de seguimiento puede usar el contexto de la conversación activa. “Nueva conversación” elimina el contexto previo; al terminar o expirar la sesión Moodle no queda contexto restaurable ni historial persistente.
10. Las pruebas cubren acceso permitido y denegado para estudiante, docente y usuario con permisos de alcance general; además, cubren aserciones vencidas/alteradas, filtrado documental previo a generación, consultas entre múltiples cursos, cierre de sesión y eliminación de contexto.

## Dependencias de entrega

- Acordar y probar el contrato de petición firmada entre el plugin y RAG, incluyendo la forma de entregar contexto académico autorizado.
- Clasificar el corpus que se use en la demo o piloto. El corpus institucional actual no demuestra cobertura ni calidad de documentos oficiales.
- Confirmar la versión real del sitio Moodle antes de declarar compatibilidad de despliegue.
