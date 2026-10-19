# Verificación conversacional y resistencia a abuso

Status: in-progress

## Objetivo

Comprobar el comportamiento con pruebas semánticas y recorridos reales, incluyendo instrucciones maliciosas en mensajes y documentos.

## Criterios de aceptación

Todos los recorridos de spec; paráfrasis fuera del prompt de ejemplo; permisos y sesiones; inyección directa/documental; rechazo de operaciones y salida fuera de ámbito; suites existentes y reporte real.

## Dependencias

01, 02, 03, 04, 05. Véase [spec.md](../spec.md).

## Estado

Alcance conjunto aprobado explícitamente por el usuario. Listo para implementar
cuando se cumplan las dependencias, respetando la spec y los límites acordados.

## Comments

Implementación y verificación en curso. El flujo firmado, las lecturas nativas,
las respuestas verificadas y el plan semanal ya están conectados; falta cerrar
la revisión final y registrar los recorridos reales de aceptación.

2026-10-06: código implementado y revisado; suite RAG 242 pruebas sin omisiones.
La ejecución se cerró a petición del usuario. La aceptación final sigue pendiente:
el tramo documental responde con calendario de tareas a una consulta de horario
de tutoría. Este fallo y las comprobaciones restantes están registrados en
[verification.md](../verification.md). No se declara aceptación integral satisfactoria.

2026-10-19: las pruebas simuladas cubren el contrato REST de Gemini, el uso del endpoint
`generateContent`, la separación de tipos de embedding y la ausencia de clave. Para cerrar
este ticket falta configurar la clave del entorno local y recorrer Moodle + Gemini, incluida
la consulta de horario de tutoría y la migración del índice completo.

2026-10-19: esta nota anterior quedó parcialmente obsoleta: el ticket 03 terminó la
migración/verificación del índice Gemini y el ticket 04 corrigió el horario de tutoría.
Se amplió `dev/moodle/smoke_browser.py` con `--ticket06`, un repro acotado `--ticket06-mixed`,
un ataque directo de extracción de claves y reintentos con espera para el error genérico
de indisponibilidad. El ataque directo mixto y la inyección documental pasaron con Gemini
real. El recorrido completo llegó a 56 consultas válidas; también detectó una respuesta
documental intermitente, que pasó en el repro acotado y en la siguiente ejecución completa.
La ejecución integral no terminó: la API registró `gemini_throttled`; una repetición agotó
los reintentos disponibles desde el saludo inicial. RAG pasó 260 pruebas sin omisiones y Moodle pasó
42 pruebas con 209 aserciones. Véase [ticket06-browser.json](../ticket06-browser.json).
El estado permanece `in-progress` hasta obtener un recorrido integrado completo.
