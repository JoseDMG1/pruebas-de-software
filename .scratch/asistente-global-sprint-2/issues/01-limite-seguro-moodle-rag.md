# Establecer el límite autenticado entre Moodle y RAG

Status: ready-for-agent

## Objetivo

Hacer que las consultas del asistente lleguen al RAG desde el servidor Moodle con una identidad y contexto autorizados que el RAG pueda verificar. Esta es la base para impedir suplantación de usuario y para limitar la recuperación documental antes de generar texto.

## Requisitos

- Mantener la credencial de servicio solo en configuración del servidor Moodle; nunca exponerla al navegador.
- Aceptar consultas del asistente solo con una aserción firmada de corta duración, emitida por el plugin Moodle.
- La identidad y el contexto de curso deben originarse en la sesión Moodle autenticada y en permisos calculados por Moodle, no en valores arbitrarios enviados por el navegador.
- El contrato debe permitir incluir el contexto académico mínimo autorizado que Moodle obtuvo para responder la pregunta.
- Rechazar peticiones sin credencial/aserción válida, vencidas o con campos de identidad/contexto alterados.
- No registrar preguntas, datos académicos personales ni credenciales en logs ordinarios.

## Criterios de aceptación

- El endpoint RAG protegido rechaza una llamada anónima y una aserción con firma inválida o vencida.
- Una prueba que altera usuario o cursos sin volver a firmar la aserción no obtiene datos ni documentos adicionales.
- El plugin puede autenticar una llamada servidor a servidor y el navegador no recibe la credencial ni la aserción de servicio.
- El contrato documenta emisor, destinatario, expiración, usuario, alcance de cursos, datos académicos permitidos, errores y rotación de claves.
- La suite existente para llamadas internas/demo conserva un modo de desarrollo claramente separado del endpoint de integración protegido; no se abre el endpoint de Moodle sin autenticación por conveniencia.

## Dependencias

Base para los tickets 02–05. Coordinar el contrato con el plugin Moodle antes de congelar campos de API.
