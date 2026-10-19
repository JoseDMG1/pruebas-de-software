# Lecturas autorizadas y guías del portal

Status: done

## Objetivo

Ejecutar planes validados en Moodle; recuperar resultados completos y documentación pertinente; incorporar guías verificadas de uso del portal.

## Criterios de aceptación

Permisos nativos por cada lectura; roles declarados sin efecto; paginación sin duplicados; errores frente a vacíos; guías versionadas con cobertura explícita; secretos fuera de navegador/modelo.

## Dependencias

01, 02. Véase [spec.md](../spec.md).

## Estado

Implementado y verificado el 2026-10-19 con Moodle y Gemini reales.
Evidencia y límites en [verification.md](../verification.md).

## Comments

Implementación y verificación en curso. El flujo firmado, las lecturas nativas,
las respuestas verificadas y el plan semanal ya están conectados; falta cerrar
la revisión final y registrar los recorridos reales de aceptación.

2026-10-06: código implementado y revisado; suite RAG 242 pruebas sin omisiones.
La ejecución se cerró a petición del usuario. La aceptación final sigue pendiente:
el tramo documental responde con calendario de tareas a una consulta de horario
de tutoría. Este fallo y las comprobaciones restantes están registrados en
[verification.md](../verification.md). No se declara aceptación integral satisfactoria.

2026-10-19: el índice de consulta migra a Gemini Embeddings `gemini-embedding-001` con
768 dimensiones. Ejecutar `rag init-db` y `rag prepare-gemini-index` para crear el nuevo
espacio a partir de los fragmentos almacenados; los espacios antiguos no se mezclan.

2026-10-19: ante un nuevo HTTP 503 por alta demanda de Gemini, se avanzó con la revisión
de lecturas y permisos. Pasó el contrato PHP del cliente servidor y la suite nativa Moodle
`academic_context_provider_test.php`: 18 pruebas, 100 aserciones. Se comprobaron permisos
efectivos, notas y entregas visibles, grupos separados y revocación de acceso entre páginas.
También pasaron 81 pruebas RAG de autenticación, interpretación local y adaptador Gemini.
La guía sigue acotada a Assignment y no se repitió el navegador. El ticket permanece
`in-progress`: pendientes la integración con Gemini real y la verificación del índice migrado.

2026-10-19 — Cierre: índice Gemini preparado (20/20 fragmentos, 768 dimensiones),
reanudación e idempotencia verificadas y permisos filtrados antes de calcular distancias.
Navegador real satisfactorio: acceso anónimo denegado, aislamiento entre alumnos,
documento autorizado, notas docentes, cursos paginados y guía de Assignment contrastada
con Moodle sin guardar entregas. Un rol declarado no concede acceso.
Evidencia: [índice](../ticket03-index.json), [navegador](../ticket03-browser.json).
La aceptación integral y los criterios de los otros tickets siguen pendientes.
