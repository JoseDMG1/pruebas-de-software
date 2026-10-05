# Cliente servidor del asistente académico

El plugin firma las consultas en Moodle y las envía directamente al RAG con la sesión del usuario actual. La URL y el secreto compartido se configuran únicamente en el `config.php` del servidor Moodle; el plugin no los guarda en tablas de configuración ni los renderiza en páginas.

```php
$CFG->local_acadassistant_rag_url = getenv('MOODLE_RAG_URL') ?: '';
$CFG->local_acadassistant_rag_shared_secret = getenv('MOODLE_RAG_SHARED_SECRET') ?: '';
```

Use HTTPS entre Moodle y RAG, excepto en desarrollo sobre loopback. Genere un secreto aleatorio de al menos 32 caracteres, por ejemplo con `openssl rand -hex 32`, y configure el mismo valor como `MOODLE_SERVICE_SECRET` en RAG. No lo incluya en el repositorio ni en el JavaScript o HTML del asistente.

## Petición firmada

El plugin hace `POST /api/v1/chat/query` con un cuerpo JSON que contiene `query` y `academic_context`. El encabezado `Authorization: Bearer` lleva un JWT HS256 con emisor `moodle`, audiencia `rag-service`, el ID del usuario Moodle actual en `sub`, los IDs de curso autorizados en `courses`, `iat`, `exp`, un `jti` aleatorio y el SHA-256 hexadecimal del cuerpo HTTP exacto en `body_sha256`. El plugin emite tokens válidos por 60 segundos; RAG acepta como máximo 120 segundos.

El cliente comprueba `can_access_course` para cada curso antes de firmar, confirma que la sesión pertenece al mismo usuario para el que fue creado y obtiene `sub` de `$USER`; no recibe un ID de usuario desde el navegador. El contrato limita `academic_context` a tres categorías: `courses` para cursos visibles al usuario, `assignments` para entregas/fechas/estados visibles y `grades` para calificaciones que Moodle permite consultar. Moodle solo debe obtener en vivo los datos académicos mínimos necesarios para esa pregunta. Los datos de otra persona requieren una capacidad efectiva de Moodle para verlos; no se incluyen datos de perfil ajenos ni se confía en el cargo declarado por el usuario. Pagos y matrícula quedan fuera del contexto de Sprint 2. El calendario académico institucional procede del corpus documental, no de estos datos personales. El `body_sha256` vincula pregunta y contexto al token e impide cambiarlos después de firmar.

RAG responde `401` para aserciones ausentes, inválidas, vencidas o con cuerpo distinto, `422` para cuerpos que no cumplen el contrato y `503` cuando no tiene un secreto de servicio configurado. La rotación requiere actualizar el mismo secreto en Moodle y RAG; prográmela como una operación coordinada.

El RAG filtra los documentos de curso en PostgreSQL antes de recuperar fragmentos, según los IDs firmados en `courses`; los documentos institucionales comunes siguen disponibles para toda cuenta autenticada. Moodle es la fuente confiable de existencia de cursos: exporte su catálogo con `cli/export_course_catalog.php` y sincronícelo en RAG con `rag sync-courses`. Cada documento nuevo requiere clasificación explícita durante la ingesta. El campo `academic_context` aún no se usa para generar respuestas; esa integración pertenece al ticket 03.

## Prueba del contrato

Desde la raíz del workspace, ejecutar el contrato PHP autónomo con:

```bash
docker run --rm \
  -v "$PWD/moodle/public/local/acadassistant:/work" \
  php:8.3-cli php /work/tests/client_contract.php
```

El contrato no requiere una instalación Moodle ni una conexión RAG; comprueba el cliente servidor y el formato que comparte con el verificador Python.
