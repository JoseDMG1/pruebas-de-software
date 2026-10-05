# Respuestas académicas confiables del asistente Moodle

Status: approved

## Problema

El asistente puede negar información aunque Moodle entregue los cursos del usuario,
y atribuir tareas o notas a documentos que no las respaldan. La fuente actual no
obtiene docentes. Las pruebas de transporte y permisos no detectan todos estos errores.

## Objetivo y alcance acordado

Entender preguntas en lenguaje natural sobre cursos, tareas, entregas, calificaciones,
calendario y docentes visibles, consultar datos autorizados en vivo y responder
con hechos verificables. Mantener el filtro documental y las capacidades efectivas
según ADR-0001. Pagos personales, escrituras en Moodle e historial persistente
siguen fuera de alcance.

## Comportamiento

- «Mis cursos» corresponde a matrícula vigente; acceso general no equivale a matrícula.
- «Qué cursos puedo consultar» corresponde al acceso efectivo. «Los que enseño»
  corresponde a responsabilidades docentes, no al cargo global declarado.
- Docentes visibles: nombres y curso únicamente, respetando visibilidad de participantes
  y restricciones de grupos. No limitar la lista a los contactos publicados.
- «Qué tareas tengo» devuelve por defecto pendientes, con curso y vencimiento.
  «Todas» o «entregadas» cambia el filtro explícitamente. Un borrador no está presentado.
- Una lectura completa y autorizada sin registros es un resultado vacío conocido:
  «no tienes tareas pendientes». Un fallo de lectura nunca equivale a cero registros.
- Reconocer expresiones equivalentes como cursos/materias/matrícula. Si la intención
  no es clara, pedir aclaración en vez de afirmar que no existe información.
- Un seguimiento inequívoco puede heredar filtros; una pregunta independiente
  cambia de tema. Una referencia a varias tareas pide aclaración.
- Preguntas mixtas reciben respuestas por parte: contestar lo disponible y explicar
  el límite restante. Distinguir fuera de alcance, error de consulta y datos ausentes;
  no revelar identidades ni existencia de recursos restringidos.
- Los datos académicos se atribuyen a Moodle. Una cita documental solo respalda
  afirmaciones obtenidas de ese documento. Mantener ambas procedencias en respuestas mixtas.
- Una lista incompleta se identifica como parcial y permite continuar en orden estable,
  sin duplicados. No afirmar que contiene todos los registros sin comprobarlo.
- Contexto y continuación son temporales y por usuario. Nueva conversación, logout
  o expiración eliminan todo estado; cada consulta vuelve a comprobar permisos.

## Propuesta de implementación para revisión

1. Interpretar intención y filtros mediante un contrato estructurado de operaciones
   soportadas. El modelo puede interpretar lenguaje natural; Moodle sigue siendo
   la autoridad y valida cada operación y alcance. No exigir palabras exactas.
2. Obtener resultados estructurados con procedencia, estado de consulta y completitud.
   Ampliar las fuentes para matrícula, responsabilidad docente y docentes visibles.
   La selección por pregunta no debe reducir indebidamente el acceso documental permitido.
3. Componer las respuestas académicas concretas desde esos resultados controlados.
   No dejar que generación libre sustituya una lista disponible por una abstención
   ni cambie nombres, fechas, notas o estados. Mantener generación documental
   con evidencia separada y composición explícita para preguntas mixtas.
4. Conservar el contrato firmado Moodle–RAG, límites de petición y contexto temporal;
   revisar su extensión compatible cuando se introduzcan operaciones y docentes.

## Verificación requerida

- Caso exacto reportado: tareas → cuotas → profesores → cursos → cursos.
- «Qué cursos tengo» responde Algebra 101 y Biologia 102 para estudiante1,
  tanto en sesión nueva como después de negativas. Variantes naturales equivalentes.
- Una autoridad con acceso global no recibe todos los cursos como matrículas propias.
- Docentes visibles y ocultos por permisos/grupos; curso sin docente visible.
- Tareas pendientes, borradores, entregadas, cero pendientes y fallo de lectura.
- Seguimiento claro, referencia ambigua y cambio de tema; sin heredar cursos incorrectos.
- Preguntas mixtas académicas/documentales/fuera de alcance y citas pertinentes.
- Más registros que el límite: aviso de parcialidad, continuación sin duplicados,
  revalidación de permisos y borrado del estado al terminar la conversación.
- Pruebas automatizadas de contratos/permisos y recorrido real Moodle + modelo local;
  no declarar éxito semántico solo porque el transporte devuelve HTTP 200.

## Confirmación

Alcance consolidado confirmado por el usuario. Tickets listos para implementar
en el orden de sus dependencias.
