# Respuestas académicas confiables

Status: resolved

## Decisiones confirmadas

- Responder cuando los datos autorizados disponibles basten; no aceptar una abstención injustificada del modelo como resultado correcto.
- Las negativas anteriores no deben impedir responder una pregunta nueva.
- «Mis cursos» significa cursos con matrícula vigente; «cursos que puedo consultar» corresponde al acceso efectivo; «cursos que enseño» corresponde a responsabilidades docentes.
- Incluir nombres de docentes por curso cuando Moodle permita verlos, sin datos personales adicionales. Explicar por curso si no hay docente asignado o visible.
- Mostrar docentes visibles en Moodle según permisos y grupos; no limitar la lista a contactos publicados.
- Pedir aclaración cuando una referencia de seguimiento tenga varias interpretaciones posibles; reconocer cambios de tema.
- Contestar las partes cubiertas de una pregunta mixta y explicar por separado las limitaciones de las restantes.
- Indicar cuándo una lista es parcial y permitir continuar con orden estable y sin duplicados; no afirmar completitud sin comprobarla.
- Mantener autorización en Moodle y pagos personales fuera de Sprint 2, según ADR-0001.

## Hechos de la investigación

- El proveedor entrega cursos, pero la generación puede descartarlos como información insuficiente.
- La validación de citas documentales no verifica que respalden cada afirmación académica.
- No existe todavía una fuente de docentes en el contrato académico.
- Los contactos publicados de Moodle y los participantes docentes visibles son conjuntos distintos.
- Las fuentes tienen límites de registros; no se debe prometer una lista completa sin verificarlo.

## Últimas decisiones confirmadas

- Reconocer formulaciones equivalentes en lenguaje natural para las consultas soportadas. Ante intención incierta, pedir aclaración sin afirmar ausencia de datos.
- «Qué tareas tengo» muestra por defecto pendientes de entrega, con curso y vencimiento; «todas» y «entregadas» solicitan esos estados explícitamente.
- Una consulta autorizada, completa y sin pendientes debe responder que no hay tareas pendientes.

## Cierre

El usuario confirmó el alcance consolidado. La spec está aprobada y los cuatro
tickets están listos para implementar según sus dependencias.

La especificación aprobada está en `spec.md`.
