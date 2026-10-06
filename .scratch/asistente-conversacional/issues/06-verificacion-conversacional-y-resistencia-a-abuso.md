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
