# Mantener contexto solo durante la conversación actual

Status: ready-for-agent

## Objetivo

Permitir preguntas de seguimiento dentro de la conversación activa sin crear un historial persistente de conversaciones.

## Requisitos

- Asociar el contexto temporal a la identidad autenticada y a una conversación activa.
- Permitir usar mensajes previos de esa misma conversación para resolver referencias y preguntas de seguimiento.
- “Nueva conversación” elimina el contexto previo y comienza sin recuperar mensajes de conversaciones anteriores.
- Cerrar o dejar expirar la sesión Moodle termina y elimina el contexto de la conversación.
- No exponer ni permitir enumerar contextos de otras identidades; no guardar una lista de conversaciones archivadas.
- Mantener el contexto temporal acotado a la conversación; no mezclar sus mensajes con datos académicos no autorizados.

## Criterios de aceptación

- Una pregunta de seguimiento en la conversación activa puede referirse a la respuesta previa.
- Tras “Nueva conversación”, una pregunta de seguimiento no puede usar el contenido anterior.
- Tras cerrar o expirar Moodle, no se puede restaurar el contexto anterior y la siguiente sesión empieza vacía.
- No existe una ruta de historial para recuperar conversaciones terminadas.
- Las pruebas cubren aislamiento entre usuarios, reinicio de conversación y expiración/cierre de sesión.

## Dependencias

Requiere que el contrato RAG soporte identidad autenticada y el estado efímero asociado, y que la página global exponga las acciones de conversación del ticket 04.
