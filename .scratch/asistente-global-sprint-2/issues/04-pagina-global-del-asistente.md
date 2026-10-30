# Publicar el asistente en la navegación global de Moodle

Status: ready-for-agent

## Objetivo

Dar acceso al chat desde la navegación global del sitio para cuentas personales autenticadas, sin exigir entrar a un curso. La consulta abarca los cursos autorizados de la persona y puede limitarse a un curso cuando la pregunta lo indique.

## Requisitos

- Integrar una página global del sitio siguiendo el mecanismo de plugin compatible con Moodle.
- Denegar acceso a invitados y requerir la sesión personal Moodle.
- Enviar preguntas al endpoint protegido RAG desde el servidor Moodle, nunca con una credencial del RAG en JavaScript/navegador.
- Mostrar respuestas, fuentes documentales, procedencia de datos Moodle, errores de servicio y respuestas por falta de evidencia.
- Permitir iniciar una conversación nueva y hacer preguntas de seguimiento en la conversación actual.
- Mantener accesibilidad, traducciones y convenciones de navegación del Moodle objetivo.

## Criterios de aceptación

- Un usuario autenticado encuentra el chat desde la navegación global y puede preguntar por información permitida a través de más de un curso.
- No se requiere abrir un curso ni seleccionar uno antes de la primera pregunta.
- Una pregunta que identifica un curso limita los datos y documentos utilizados a ese curso y a fuentes institucionales comunes.
- Un invitado o sesión cerrada no puede usar la página ni invocar el servicio del plugin.
- La interfaz nunca recibe secretos del RAG y presenta procedencia suficiente para distinguir documento institucional, calendario Moodle y dato académico Moodle.
- La página no ofrece lista ni navegación por conversaciones pasadas.

## Dependencias

Se integra con los contratos de los tickets 01–03. Confirmar la versión real desplegada antes del despliegue; usar Moodle 5.3dev solo como objetivo provisional de desarrollo.
