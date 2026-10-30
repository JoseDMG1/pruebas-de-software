# Campaña ampliada de rendimiento

Resultados por ejecución. No se eliminan respuestas lentas ni fallos. La calibración del arnés se identifica por separado. Las etapas http-* usan el controlador autenticado de Moodle pero excluyen el navegador: no se equiparan al tiempo desde clic hasta respuesta visible.

| Etapa | Cuentas | Solicitudes medidas | Duración medida (s) | Correctas ≤10 s | p95 (s) | p99 (s) | Errores | Completa / cumple |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| baseline-1 | 1 | 4 | 25.787 | 75.0% | 7.1744 | 7.1744 | 1 | No / No |
| baseline-1-validado | 1 | 10 | 63.894 | 100.0% | 7.4595 | 7.4595 | 0 | Sí / Sí |
| nivel-10 | 10 | 290 | 301.102 | 100.0% | 7.1629 | 7.5217 | 0 | Sí / Sí |
| nivel-25 | 25 | 500 | 317.754 | 99.4% | 8.5548 | 9.2605 | 0 | Sí / Sí |
| nivel-50 | 50 | 550 | 315.777 | 61.636% | 13.0916 | 14.5708 | 0 | Sí / No |
| recuperacion-10 | 10 | 300 | 306.824 | 100.0% | 7.0112 | 7.1911 | 0 | Sí / Sí |
| sostenida-25 | 25 | 225 | 161.485 | 97.333% | 8.395 | 9.2019 | 6 | No / No |
| pico-10-25-10 | 25 | 0 | — | —% | — | — | 0 | No / No |
| mixta-10 | 10 | 0 | — | —% | — | — | 0 | No / No |
| http-1 | 1 | 0 | — | —% | — | — | 0 | No / No |
| http-control-academico-1 | 1 | 3 | 10.332 | 100.0% | 3.5364 | 3.5364 | 0 | Sí / Sí |

La aprobación requiere ejecución completa, cero errores y ≥95% correctas en ≤10 s. Calentamiento y acceso quedan fuera de la latencia; reinicios de conversación y pausas declaradas forman parte del throughput. Los resúmenes de recursos y disponibilidad filtran la fase medida; los JSON conservan también la preparación. No es un SLA.

La calibración baseline-1 tuvo un falso negativo de gratuidad no solicitada; ver ajustes-arnes.md. No se atribuye al producto. Los resultados posteriores usan correo/cita/fuente como criterio de esa pregunta.

## Recursos y límites por etapa

- baseline-1: CPU media 18.72%, pico muestreado 19.44%; RAM disponible mínima 5772.5 MiB; swap máximo 0.0 MiB; RSS agregado de procesos de navegador 0.0 MiB (incluye memoria compartida y otros navegadores del host, no es memoria exclusiva). Sondas conjuntas correctas 4/4. Motivo de parada: over_5_percent_errors_in_last_minute. Fallos de calentamiento: 0.
- baseline-1-validado: CPU media 24.28%, pico muestreado 36.4%; RAM disponible mínima 5614.6 MiB; swap máximo 0.0 MiB; RSS agregado de procesos de navegador 637.0 MiB (incluye memoria compartida y otros navegadores del host, no es memoria exclusiva). Sondas conjuntas correctas 9/9. Motivo de parada: finalización prevista. Fallos de calentamiento: 0.
- nivel-10: CPU media 56.21%, pico muestreado 71.38%; RAM disponible mínima 4041.1 MiB; swap máximo 0.9 MiB; RSS agregado de procesos de navegador 2972.4 MiB (incluye memoria compartida y otros navegadores del host, no es memoria exclusiva). Sondas conjuntas correctas 41/41. Motivo de parada: finalización prevista. Fallos de calentamiento: 0.
- nivel-25: CPU media 79.17%, pico muestreado 95.06%; RAM disponible mínima 2159.7 MiB; swap máximo 595.4 MiB; RSS agregado de procesos de navegador 6788.8 MiB (incluye memoria compartida y otros navegadores del host, no es memoria exclusiva). Sondas conjuntas correctas 43/43. Motivo de parada: finalización prevista. Fallos de calentamiento: 0.
- nivel-50: CPU media 87.28%, pico muestreado 99.87%; RAM disponible mínima 1195.2 MiB; swap máximo 3169.0 MiB; RSS agregado de procesos de navegador 12079.4 MiB (incluye memoria compartida y otros navegadores del host, no es memoria exclusiva). Sondas conjuntas correctas 39/40. Motivo de parada: finalización prevista. Fallos de calentamiento: 0.
- recuperacion-10: CPU media 55.42%, pico muestreado 66.37%; RAM disponible mínima 5974.9 MiB; swap máximo 2420.5 MiB; RSS agregado de procesos de navegador 2926.7 MiB (incluye memoria compartida y otros navegadores del host, no es memoria exclusiva). Sondas conjuntas correctas 42/42. Motivo de parada: finalización prevista. Fallos de calentamiento: 0.
- sostenida-25: CPU media 71.77%, pico muestreado 94.55%; RAM disponible mínima 3881.1 MiB; swap máximo 2233.2 MiB; RSS agregado de procesos de navegador 6217.9 MiB (incluye memoria compartida y otros navegadores del host, no es memoria exclusiva). Sondas conjuntas correctas 21/21. Motivo de parada: over_5_percent_errors_in_last_minute. Fallos de calentamiento: 0.
- pico-10-25-10: CPU media None%, pico muestreado None%; RAM disponible mínima None MiB; swap máximo None MiB; RSS agregado de procesos de navegador None MiB (incluye memoria compartida y otros navegadores del host, no es memoria exclusiva). Sondas conjuntas correctas 0/0. Motivo de parada: warmup_failed. Fallos de calentamiento: 7.
- mixta-10: CPU media None%, pico muestreado None%; RAM disponible mínima None MiB; swap máximo None MiB; RSS agregado de procesos de navegador None MiB (incluye memoria compartida y otros navegadores del host, no es memoria exclusiva). Sondas conjuntas correctas 0/0. Motivo de parada: warmup_failed. Fallos de calentamiento: 4.
- http-1: CPU media None%, pico muestreado None%; RAM disponible mínima None MiB; swap máximo None MiB; RSS agregado de procesos de navegador None MiB (incluye memoria compartida y otros navegadores del host, no es memoria exclusiva). Sondas conjuntas correctas 0/0. Motivo de parada: warmup_failed. Fallos de calentamiento: 1.
- http-control-academico-1: CPU media None%, pico muestreado None%; RAM disponible mínima 8005.5 MiB; swap máximo 2061.5 MiB; RSS agregado de procesos de navegador 0.0 MiB (incluye memoria compartida y otros navegadores del host, no es memoria exclusiva). Sondas conjuntas correctas 1/1. Motivo de parada: finalización prevista. Fallos de calentamiento: 0.

## Fases del pico

