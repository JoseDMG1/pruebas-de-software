# Respuestas legibles y estructuradas

Status: completed

## Objetivo

Presentar las respuestas del asistente en bloques breves y legibles, en particular listas de
tareas, cursos, calificaciones y fechas; conservar citas y enlaces del chat.

## Criterios de aceptación

- [x] Separar encabezados y datos de cada actividad en líneas legibles.
- [x] Mostrar las fechas en español y con día y mes completos.
- [x] Mantener la respuesta original útil para referencias y seguimientos.
- [x] Dar a los destinos Moodle una presentación clara sin cambiar su URL ni su autorización.
- [x] No interpretar HTML o enlaces arbitrarios generados por el modelo.
- [x] Verificar un listado real del chat y ejecutar las suites automatizadas ya acordadas.

## Verificación

- Moodle real: 9 tareas aparecen en una lista y cada una conserva su curso, estado y fecha.
- Chat real: `smoke_browser.py --ticket10` completo; latencia observada 3,38 s.
- RAG: 260 pruebas pasaron y 14 se omitieron; Ruff sin errores.
- Moodle: 53 pruebas del plugin pasaron con 243 aserciones.
