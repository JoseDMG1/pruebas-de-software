# Plan semanal académico personalizado

Status: in-progress

## Objetivo

Preparar y ajustar un plan semanal desde tareas pendientes reales y disponibilidad declarada, conservando vencimientos y restricciones.

## Criterios de aceptación

Consulta antes de pedir disponibilidad; fechas y zona horaria; cero/vencidas/sin fecha/prórrogas; páginas completas; supuestos explícitos; parcialidad visible; no escrituras ni persistencia.

## Dependencias

03, 04. Véase [spec.md](../spec.md).

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

2026-10-19: el plan continúa usando el flujo de consulta existente; interpretación y
respuesta se ejecutan con Gemini. Falta validar este recorrido con la API real.
