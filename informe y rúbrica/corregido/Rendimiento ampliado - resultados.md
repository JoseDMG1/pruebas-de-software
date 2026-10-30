# Resultados de la campaña ampliada de rendimiento — 29/10/2026

**Se midió el chat con hasta 50 cuentas distintas. Veinticinco aprobaron la carga breve; cincuenta incumplieron latencia. La estabilidad sostenida a 25 no aprobó porque se agotó la cuota diaria de embeddings.** No se declara capacidad sostenida de 25 ni capacidad de 75/100.

| Etapa de navegador | Cuentas distintas | Consultas medidas | Tiempo medido | Correctas en ≤10 s | p95 | Resultado |
|---|---:|---:|---:|---:|---:|---|
| Referencia ampliada | 10 | 290 | 301,102 s | 100% | 7,1629 s | Aprobada |
| Nivel superior | 25 | 500 | 317,754 s | 99,4% | 8,5548 s | Aprobada para esta carga breve |
| Límite observado | 50 | 550 | 315,777 s | 61,636% | 13,0916 s | No cumple latencia; cero errores |
| Recuperación a carga menor | 10 | 300 | 306,824 s | 100% | 7,0112 s | Aprobada antes del agotamiento de cuota |
| Sostenida, objetivo 900 s | 25 | 225 | 161,485 s | 97,333% | 8,395 s | No aprobada: seis errores; se activó parada |

Estas cinco fases reúnen **1.865 consultas medidas**. Se excluyen calentamientos y calibración del total. Las respuestas se comprobaron con criterios mínimos de contenido y acceso; una respuesta no vacía dejó de ser suficiente para aprobar.

## Qué cambió respecto de la prueba anterior

- Cuentas distintas `carga001`…`carga100`, preparadas localmente a partir de dos perfiles de matrícula. Se midieron hasta 50; no se afirma haber medido cien.
- Cinco preguntas rotatorias: nota mínima, cursos, docentes, orientación psicológica y calendario. Se verificaron hechos, fuente o destino y los cursos permitidos/prohibidos de cada perfil.
- Medición desde envío hasta respuesta visible, sin reintentos del arnés. Se conservaron respuestas lentas, errores y muestras originales.
- Registro de p50/p95/p99, máximo, solicitudes/s, CPU, RAM, swap, contenedores y salud HTTP. Login y calentamiento se excluyeron de latencia; pausas y reinicios se incluyeron en throughput.
- Etapas secuenciales: no se ejecutaron pruebas de proveedores en paralelo con una fase medida de carga.
- Once comprobaciones automatizadas del arnés aprobadas. No se reejecutaron las suites históricas completas de 295/53 pruebas, porque no se cambió el aplicativo para esta campaña.

## Dos límites diferentes

**Recursos del entorno a 50 cuentas.** El equipo de cuatro CPU lógicas y aproximadamente 11 GiB de RAM también generó la carga con Chromium. En esa fase: CPU media 87,28%, pico muestreado 99,87%, memoria disponible mínima 1.195,2 MiB y swap máximo 3.169 MiB. El resultado es del conjunto local, no una prueba de que el servidor aislado tenga exactamente ese límite. Las sondas HTTP conjuntas fueron correctas en 39/40 muestras de la fase medida, sin demostrar corrección funcional ni disponibilidad mensual.

**Cuota diaria durante la sostenida.** Los seis errores de la sostenida se registraron como `query / gemini_throttled`. Una petición diagnóstica independiente confirmó HTTP 429 y la cuota `EmbedContentRequestsPerDayPerProjectPerModel-FreeTier`, con valor 1.000 para `gemini-embedding-001`. Es la cuota observada del proyecto/modelo, no un límite universal de todas las cuentas Gemini.

La respuesta del proveedor indicó reintentar aproximadamente el **30/10/2026 a las 02:00, hora de Lima**. Es una orientación de la respuesta, no garantía de disponibilidad. Google documenta el reinicio diario a medianoche del Pacífico y los límites por proyecto. [Documentación oficial de límites](https://ai.google.dev/gemini-api/docs/rate-limits).

## Etapas bloqueadas y control posterior

- Pico de 10 → 25 → 10: 7/25 fallos de calentamiento; cero solicitudes medidas.
- Mezcla ampliada con tareas, planificación y consultas combinadas: 4/10 fallos de calentamiento; cero solicitudes medidas. Una respuesta devolvió los cursos autorizados pero reconoció que no podía verificar la parte documental: se contabilizó como incompleta, no como éxito.
- Calibración HTTP documental: falló su única petición de calentamiento; no se iniciaron las cargas HTTP de 50/100.
- Control HTTP académico posterior: tres consultas de cursos, docentes y calendario respondieron correctamente con una cuenta; p95 3,5364 s. Solo verifica continuidad de esas lecturas sin embeddings, no capacidad concurrente ni tiempo de renderizado.

La estabilidad de quince minutos no quedó validada. Se conservan los intentos y su causa; no se reemplazan por una mezcla más sencilla para obtener una aprobación.

## Estado del informe y del Excel

Los 36 planes siguen presentes y clasificados. CP-011 y CP-012 amplían su alcance a los niveles y estabilidad nuevos y quedan como **FALLÓ**; el resultado histórico a diez sesiones se conserva por separado. Los otros 34 conservan su resultado de referencia: no significa que se hayan reejecutado ni que una consulta documental funcione ahora con cuota agotada.

Se incorporaron DEF-08 (cuota diaria, abierto) y DEF-09 (límite local de latencia a 50, diagnóstico parcial). La medición inicial de diez sesiones y dos cuentas sigue disponible como referencia, junto con los fallos anteriores y sus repruebas.

## Evidencia y reproducción

Fuentes en `dev/validation/capacity_*.py` y `dev/moodle/load-users.php`. Evidencia completa en `.scratch/rendimiento-ampliado/evidencias/`; copia de entrega en `informe y rúbrica/corregido/evidencias/rendimiento-ampliado/`.

Los archivos `nivel-10.json`, `nivel-25.json`, `nivel-50.json`, `recuperacion-10.json`, `sostenida-25.json`, `pico-10-25-10.json`, `mixta-10.json`, `cuota-gemini.json` y `diagnostico-cuota.md` permiten auditar parámetros, respuestas, estados, recursos y causas. `resultados.md` contiene la tabla ampliada y `resumen.json` sus valores estructurados.

Para cerrar el trabajo pendiente se necesita cuota suficiente disponible durante toda la ventana, y repetir sostenida, pico y mezcla ampliada. Las salidas deben tener nombres nuevos. Ejemplo desde la raíz, después de verificar cuota:

```bash
PLAYWRIGHT_BROWSERS_PATH=rag-service/.cache/ms-playwright rag-service/.venv/bin/python dev/validation/capacity_chat.py --stage sostenida-25-reprueba --users 25 --seconds 900 --requests 250 --pause 3 --output .scratch/rendimiento-ampliado/evidencias/sostenida-25-reprueba.json
```

No se modificó el aplicativo, el modelo o la facturación para conseguir un resultado favorable. La cuota y los recursos son parte del comportamiento observado del sistema actual.
