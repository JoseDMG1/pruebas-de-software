# Interpretación natural y contexto temporal

Status: done

## Objetivo

Interpretar intención y referencias con Gemini y JSON validado antes de filtrar contexto o consultar fuentes.

## Criterios de aceptación

Variantes nuevas, reformulaciones, cambios de tema y ambigüedad; disponibilidad pertinente solo en sesión; límites de llamadas y errores explícitos; no depender de coincidencia literal.

## Dependencias

01. Véase [spec.md](../spec.md).

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

2026-10-19: proveedor conversacional migrado a Gemini `gemini-flash-latest` mediante
`v1beta/models/gemini-flash-latest:generateContent`. La clave queda en el servidor RAG;
la verificación con API real queda pendiente porque no hay una clave configurada en este entorno.

2026-10-19: corrección de estado tras configurar la clave. Los metadatos del modelo respondieron
HTTP 200 y confirman `generateContent`; embeddings también respondió. La generación de chat, sin
embargo, agotó el timeout y una solicitud mínima obtuvo HTTP 503 `UNAVAILABLE` por alta demanda.
La lógica local de interpretación/contexto temporal pasó sus suites con modelos simulados; falta
validarla con una respuesta real de Gemini. Ticket permanece `in-progress`.

2026-10-19: el usuario autorizó reintentos y una alternativa estable. `gemini-3.5-flash-lite`
respondió JSON `{"answer":"OK"}` en 1,96 s y nuevamente en 1,84 s, y quedó seleccionado en
el `.env` local. Se añadieron reintentos acotados y se actualizó el envío del esquema al formato
`responseFormat.text.schema`, preservando las definiciones Pydantic. Se detectó que una primera
validación aún leía el alias `latest`; al seleccionar Flash Lite explícitamente pasaron los seis
casos reales: cursos, semana actual, próxima semana, fecha ISO, seguimiento y cambio de tema.
Se comprobaron los intervalos con el reloj de Lima y que el cambio de tema elimina el filtro de
la tarea anterior. Se confirmó al terminar el modelo efectivo en `.env`. El ticket sigue en
curso hasta completar los demás criterios y el recorrido Moodle integrado. Informe reproducible en
`../gemini-live-validation.json` y script `rag-service/scripts/check_gemini_conversation.py`.

2026-10-19 — Cierre: el validador Gemini cubre ocho casos reales con reloj fijo
de Lima, incluido seguimiento docente, cambio de tema, referencia ambigua a una tarea
y corrección de disponibilidad. Cada interpretación usó dos solicitudes de generación
y dos intentos HTTP; con --retries 1 el máximo verificado es cuatro intentos HTTP.
Las pruebas de contrato comprueban contexto previo, estado de sesión, errores del proveedor
y rechazo de planes inválidos. El artefacto de datos es sintético; no lee Moodle.
Evidencia: [ticket02-live-validation.json](../ticket02-live-validation.json).
La aceptación integral permanece pendiente de los tickets 05 y 06.
