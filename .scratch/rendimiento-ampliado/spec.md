# Campaña ampliada de rendimiento local

Status: approved

El usuario autorizó implementar y ejecutar una prueba mejor de rendimiento. Conservar evidencia anterior y no representar cargas hipotéticas como medidas.

- Chat Moodle real desde navegador, identidades distintas de prueba, permisos nativos y proveedores reales.
- Validar resultado mínimo por pregunta; errores y respuestas incorrectas cuentan como fallo.
- Mantener meta: ≥95% correctas en ≤10 s, cero errores. Registrar p50/p95/p99, extremos, throughput y recursos.
- Caracterizar niveles 1, 10, 25, 50, 75, 100; detener aumento si se degrada el servicio o el generador. No exigir alcanzar 100 a costa de saturación continuada.
- Sostenida, pico y recuperación en función del nivel observado; registrar duración efectiva y cualquier limitación.
- Resultados de cada fase en archivos independientes, parámetros y monitorización conservados. Actualizar informe/Excel con evidencia real.

## Protocolo ejecutado

Calibración de una cuenta (10 consultas); referencia de diez cuentas con al menos 100 consultas y cinco minutos; niveles superiores con al menos 500 consultas y cinco minutos. Primer nivel que incumple el objetivo detiene incrementos. Recuperación de diez cuentas durante cinco minutos. Prueba inicial de estabilidad de quince minutos al mayor nivel aprobado, con pausa de tres segundos entre rondas; no acredita la duración de una hora propuesta para una campaña posterior.

Se añade un pico controlado entre diez y el nivel estable, una mezcla de ocho temas a diez cuentas y, posteriormente y sin solapar cargas, un canal HTTP nativo Moodle sin renderizado para separar la carga del generador Chromium. Las dos modalidades se reportan separadas.
