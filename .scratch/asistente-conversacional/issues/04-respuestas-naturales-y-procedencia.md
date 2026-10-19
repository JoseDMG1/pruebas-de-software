# Respuestas naturales y procedencia verificable

Status: done

## Objetivo

Redactar respuestas relevantes desde resultados autorizados, incluyendo cortesía y confirmaciones directas, con control del ámbito y de los hechos.

## Criterios de aceptación

Saludo sin búsqueda; sí/no/limitación pertinente; no repetir listas ajenas; citas separadas; no hechos de ejemplos; solicitudes excluidas rechazadas sin desarrollarlas; salida inválida no publicada.

## Dependencias

02, 03. Véase [spec.md](../spec.md).

## Estado

Implementado y verificado el 2026-10-19. Evidencia y límites en
[verification.md](../verification.md).

## Comments

Implementación y verificación en curso. El flujo firmado, las lecturas nativas,
las respuestas verificadas y el plan semanal ya están conectados; falta cerrar
la revisión final y registrar los recorridos reales de aceptación.

2026-10-06: código implementado y revisado; suite RAG 242 pruebas sin omisiones.
La ejecución se cerró a petición del usuario. La aceptación final sigue pendiente:
el tramo documental responde con calendario de tareas a una consulta de horario
de tutoría. Este fallo y las comprobaciones restantes están registrados en
[verification.md](../verification.md). No se declara aceptación integral satisfactoria.

2026-10-19: redacción documental y académica usa Gemini `gemini-flash-latest` mediante
el mismo cliente que la interpretación. Las respuestas JSON se validan en RAG y el modelo
no recibe permisos ni credenciales.

2026-10-19 — Cierre: las respuestas conservan evidencia documental y no arrastran
el vencimiento de una tarea al cambiar a una consulta independiente de tutoría.
El flujo real desde Moodle, con Gemini, devolvió el horario del martes a las 16:00
y su cita; no repitió la fecha de entrega de la tarea seleccionada.
Regresión automatizada: test_independent_document_question_drops_previously_selected_task.
Evidencia real: [ticket04-browser.json](../ticket04-browser.json).
Este cierre no declara terminados los tickets 02, 05, 06 ni la aceptación integral.
