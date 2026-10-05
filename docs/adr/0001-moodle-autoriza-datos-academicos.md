# Moodle autoriza los datos académicos y RAG filtra documentos

**Status: accepted**

Moodle es la autoridad para autenticar a la persona y calcular sus permisos efectivos por contexto; el plugin consulta únicamente los datos académicos que esa persona puede ver y envía al servicio RAG una petición servidor a servidor con contexto mínimo y una aserción firmada de corta duración. RAG valida esa aserción y filtra documentos de curso antes de recuperar fragmentos o generar respuestas, porque una credencial de servicio compartida o un identificador enviado por el navegador no representan por sí solos autorización de una persona. La credencial permanece en el servidor Moodle; los pagos y matrículas individuales quedan fuera de Sprint 2.
