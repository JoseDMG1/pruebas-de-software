# Diseño del asistente conversacional académico

Status: resolved

## Problema reportado

«hola como estás» recibe «No encontré evidencia para esa consulta. ¿Puedes precisar qué necesitas?».
El usuario pide revisar el objetivo de ser un asistente: conversar naturalmente,
entender reformulaciones y responder a la intención, además de recuperar documentos.
Las correcciones previas cubrieron secuencias académicas concretas, pero no definieron
comportamiento social ni la frontera de orientación general sin evidencia institucional.

## Acuerdos que se conservan

- Moodle autoriza datos personales y acceso por capacidades efectivas.
- RAG filtra documentos antes de generar; no inventar hechos institucionales o personales.
- Lectura en vivo, solo lectura; credencial servidor a servidor.
- Contexto temporal de sesión; sin historial persistente.
- Pagos personales y metas de carga fuera del alcance aprobado de Sprint 2.
- Seguimientos y confirmaciones deben responder a la intención actual sin repetir información ajena.

## Decisiones de la primera ronda

- El asistente se centra en la vida universitaria; no contesta temas ajenos a ese ámbito.
- Saludos y conversación social breve solo cuando el mensaje tiene esa intención.
- La ayuda u orientación debe identificar primero qué necesita la persona y utilizar
  las fuentes pertinentes; no enviar automáticamente toda interacción a búsqueda documental.
- Organizar la semana es una consulta válida: leer las tareas sin entregar y utilizar
  esos datos para proponer un plan personalizado, no solo consejos genéricos.
- Prevenir abuso e inyección de instrucciones es un requisito. La garantía absoluta
  de ausencia de ataques no es verificable; el diseño debe mantener permisos en el
  servidor, operaciones permitidas y pruebas de resistencia. Los detalles quedan pendientes.

## Decisiones de la segunda ronda

- Ayuda permitida en esta etapa: información institucional, orientación de uso de
  Moodle, consultas académicas personales y organización del estudio.
- Tutoría de contenidos de asignaturas fuera de esta etapa: la matrícula en un curso
  no habilita por sí sola respuestas generales sobre esa disciplina.
- Al organizar la semana, consultar primero tareas pendientes y vencimientos;
  luego pedir brevemente disponibilidad. Si no puede precisarse, ofrecer un borrador
  por vencimientos con supuestos explícitos, sin inventar duraciones como datos reales.

## Decisiones de la tercera ronda

- Conversación social limitada a saludos, cortesía, despedidas y preguntas breves
  como «¿cómo estás?»; no entretenimiento o conversación general ajena al ámbito.
  No iniciar charla social cuando la intención es pedir ayuda académica.
- En mensajes mixtos, atender solo la parte universitaria permitida. Una instrucción
  maliciosa no cambia los permisos, las operaciones permitidas ni los límites de respuesta.
- Para un plan completo, recuperar las páginas necesarias de tareas y comprobar
  completitud. Si falla o no se completa, explicar qué falta, pedir acotar o reintentar
  y marcar como parcial cualquier propuesta basada en una lectura parcial.

## Hechos verificados para el plan semanal

El proveedor actual obtiene tareas visibles, estados, curso y vencimiento efectivo,
incluidas prórrogas individuales. No obtiene disponibilidad personal ni estimación
fiable de esfuerzo. La duración de un evento de calendario no equivale a esfuerzo de una tarea.

Las tareas llegan en páginas de 20 registros. `complete` informa del límite de cursos;
`has_more` informa de más páginas: ambos deben comprobarse antes de afirmar que un
plan incluye todas las tareas. La ventana semanal no está implementada para tareas.

## Decisiones de la cuarta ronda

- Uso de Moodle: incorporar guías verificadas para el portal. Si falta una instrucción
  aplicable, no inventar pasos o pantallas; explicar el límite y ofrecer ayuda respaldada.
  Las normas universitarias requieren evidencia institucional.
- «Mi semana» sin fechas: desde hoy hasta el domingo de la semana actual, según la
  zona horaria de Moodle, mostrando el intervalo. Separar vencidas y sin fecha;
  preguntar prioridad para estas últimas y considerar próximas entregas al anticipar trabajo.
- No asumir que una tarea vencida tiene prórroga ni que una entrega tardía será aceptada.

## Hechos de arquitectura verificados

Moodle actualmente interpreta, lee y luego llama RAG en una única petición. Para
interpretación por modelo antes de las lecturas se debe separar esa coordinación,
validar un nuevo contrato y eliminar el filtro previo por regex que impide enviar
contexto al modelo en preguntas no reconocidas. La integración existente permite
JSON estructurado y validado; no utiliza ni demuestra function calling nativo.
El contrato no transmite zona horaria ni fecha actual, necesarias para «esta semana».
La aserción firmada y las comprobaciones nativas de permisos se conservan.

## Acuerdo final

Ver [spec.md](spec.md) y los seis tickets en [issues/](issues/).
El usuario confirmó: «confirmo el entendimiento compartido». La spec queda aprobada
y los tickets listos para implementación según sus dependencias.

## Estado

Planificación finalizada y aprobada. Esta sesión de diseño no modifica el producto.
La implementación comienza con el ticket 01 y conserva las fronteras de autorización
y los criterios de verificación acordados.
