# Validación del prototipo del Sprint 1

El alcance incluye ingesta, recuperación básica, respuestas con fuentes y página de prueba,
utilizando exclusivamente Ollama. Se completa la entrega de prototipo funcional del PDF; la
integración Moodle y los requisitos generales de rendimiento y seguridad quedan para los
siguientes sprints.

## Comprobaciones completadas

| Comprobación | Resultado |
|---|---|
| Suite estricta con PostgreSQL y Chromium | **127 pruebas aprobadas, sin omisiones** |
| Ruff | Aprobado |
| Ingesta y migraciones 001/002 | Verificadas, esquema versión 2 |
| Espacios de embeddings y cobertura | Modelo/digest/dimensión exactos; corpus vigente completo |
| Recuperación y consistencia | Actualizaciones, borrado y rechazo de fuentes obsoletas verificados |
| API de consulta | Respuestas, referencias inválidas, entrada y errores verificados |
| Generación local | Contrato JSON, capacidad, digest, respuesta incompleta y preparación verificados |
| Página en Chromium | Espera, bloqueo de duplicados, errores, abstención y renderizado seguro verificados |
| Página desplegada con consulta real | Nota mínima 11 con fuente y fragmento del reglamento |
| Preparación del corpus repetida | Tres documentos `unchanged`, versión 1, sin duplicados |
| PostgreSQL y API Docker | Activos, `/health` HTTP 200 |
| Configuración Compose base y variantes | Validada |
| AWS, credenciales y Moodle | Sin cambios; el flujo actual no llama a AWS |

Las pruebas ordinarias simulan modelos. La evaluación adicional usa realmente los modelos de
Ollama y la API desplegada; sus resultados se registran por separado.

## Corpus, entorno y reproducción

Los modelos activos son `qwen3-embedding:0.6b` para vectores de 1024 dimensiones y `qwen2.5:3b`
para generación. Se reutiliza el contenedor Ollama existente. `.env` y Compose tienen proveedor
`ollama`; las credenciales AWS no son necesarias para este incremento.

La primera evaluación completa con `llama3.2:3b` obtuvo 19/20 coincidencias de hechos y solo
3/5 abstenciones; no cumplió la aceptación. El informe se conserva en
[evaluation-llama-results.json](evaluation-llama-results.json). También se observó una frase adicional
con un nombre de trámite incorrecto. La evaluación con `qwen2.5:3b` obtuvo 13/20 positivas y
5/5 abstenciones: tampoco cumplió la aceptación. Se conserva en
[evaluation-qwen3b-results.json](evaluation-qwen3b-results.json). Se probaron variantes de 7B y CPU,
pero las recargas por memoria de GPU y los tiempos de espera las hicieron inadecuadas para este
equipo. Se conserva `qwen2.5:3b` con instrucciones revisadas y contexto de embeddings de 2048 tokens;
las preguntas y los documentos de evaluación permanecen iguales. Los modelos instalados se conservan.

El corpus reproducible contiene matrícula, reglamento y trámites de la institución ficticia
Universidad Demo del Valle: tres documentos de tres páginas, nueve fragmentos. El antiguo PDF
sintético de ingesta también se conserva, por lo que el índice local cubre diez fragmentos actuales.
Los PDF y el entorno virtual se excluyen de Git; los textos originales, generador y preguntas
de evaluación se versionan. Los documentos permanecieron en versión 1 al repetir la preparación.

```bash
.venv/bin/rag prepare-demo
.venv/bin/rag ask '¿Cuál es la nota mínima aprobatoria?'
export PLAYWRIGHT_BROWSERS_PATH=.cache/ms-playwright
export TEST_DATABASE_URL='postgresql://rag:rag_local_dev@localhost:55432/rag'
.venv/bin/pytest -q --strict-markers --require-complete
.venv/bin/ruff check .
.venv/bin/python scripts/smoke_demo_browser.py
.venv/bin/python scripts/evaluate_demo.py
```

La API usa Python 3.12 en Docker; la suite local se ejecutó en Python 3.14. PostgreSQL está en
`127.0.0.1:55432` y la página en `http://127.0.0.1:8000/demo`. El navegador real completó una pregunta,
mostró el dato solicitado, páginas, versión y el fragmento de la fuente, y volvió a habilitar el botón.

## Evaluación real

La evaluación fija tiene veinte preguntas respondibles y cinco sin información en el corpus.
Comprueba hechos esperados y documentos citados, y guarda las respuestas completas para revisión.
Un informe interrumpido contiene `complete: false` y no acredita aceptación.

Criterios: al menos 16 de 20 positivas correctas, abstención en las cinco negativas y referencias
válidas a documentos vigentes. La evaluación del corpus ficticio no certifica calidad general.
El resultado definitivo y las latencias están en [evaluation-results.json](evaluation-results.json).

Resultado del 2 de octubre de 2026: **aceptación aprobada**. La comprobación automática encontró
los hechos esperados en 20/20 positivas. La revisión completa contra los fragmentos citados
acredita **19/20 positivas (95 %) y 5/5 abstenciones**. P17 acertó el importe y el plazo, pero cambió
«constancia de matrícula» por «duplicado de carné»; se cuenta como incorrecta. P20 incluyó datos
adicionales sustentados sobre el certificado, con colocación de citas mejorable. Las referencias
devueltas corresponden a fragmentos vigentes reales del corpus ficticio.

La mediana de las 25 consultas fue **22,863 segundos**, el percentil 95 **34,249 segundos** y la
primera consulta **87,640 segundos**. Son mediciones secuenciales locales, sin prueba de carga;
no cumplen ni acreditan el objetivo general de diez segundos. Se observaron generación en CPU y
embeddings en GPU. La selección automática y las condiciones del equipo pueden cambiar las latencias.

La evaluación completa se ejecutó contra la API local en `127.0.0.1:8001`, Python 3.14, con el mismo
código desplegado en Docker. El navegador real verificó adicionalmente `/demo` y el endpoint de la
API Docker en `127.0.0.1:8000`, Python 3.12, después del despliegue final. El servidor temporal de
evaluación se detuvo al finalizar. El informe conserva la ejecución, los digests y la revisión semántica.

## Límites del incremento

La calidad de una referencia validada no prueba que cada afirmación del modelo sea correcta.
Se conservan respuestas fallidas en el informe y se revisan semánticamente los resultados.
No se certifican todavía los objetivos generales del PDF de rendimiento bajo carga, seguridad
de despliegue o relevancia sobre documentos universitarios oficiales.

Bedrock permanece disponible en código para una futura activación explícita. La última prueba
histórica recibió `bedrock_throttled`; en este cierre no se intentaron inferencias ni cambios de cuota.
No se modificaron credenciales ni el clon Moodle. El repositorio se entrega con un commit local;
GitHub no se configura porque no existe todavía un remoto definido.
