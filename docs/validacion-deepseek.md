# Validación del asistente con DeepSeek

Fecha: 22 de octubre de 2026. Entorno local, Moodle 5.3dev, PostgreSQL/pgvector,
DeepSeek `deepseek-flash` y Gemini `gemini-embedding-001` de 768 dimensiones.

## Pruebas automatizadas

| Suite | Resultado |
| --- | --- |
| RAG: contratos, proveedores simulados, persistencia PostgreSQL y navegador | 270 aprobadas, ninguna omitida |
| Plugin Moodle: autorización, conversación, paginación y navegación | 51 pruebas, 234 aserciones, todas aprobadas |
| Ruff | Sin errores |
| `git diff --check` | Sin errores |

La suite Python genera esquemas temporales. PHPUnit usa tablas y directorio de
prueba separados. Las suites unitarias no dependen de inferencias externas.

## Navegación real

El [reporte de navegación](../.scratch/asistente-conversacional/navigation-browser.json)
registra siete consultas completas con DeepSeek y comprobación de destinos en Chromium:

- Empate entre las dos tareas con vencimiento futuro más cercano; clic en ambos enlaces.
- Curso sin acceso: no se ofrece un enlace al estudiante.
- Informe de notas personal, con su nota visible.
- Calendario nativo.
- Tablas de calificación para el docente autorizado.
- Libro docente, esperando la carga asíncrona de participantes.
- Curso disponible para dirección académica.

Los tests del plugin comprueban también prórrogas, tareas ocultas, URLs no admitidas,
escape HTML, falta de permisos, lectura parcial y vencimiento en una página posterior.

## Recorrido conversacional completo

El [reporte final](../.scratch/asistente-conversacional/ticket06-browser.json) contiene
72 consultas, `complete: true` y cero reintentos. Comprueba planificación y cambios de
horario, docentes, seguimientos, cambios de tema, aislamiento por usuario, referencias
institucionales, expiración real de sesión, cierre de sesión, lectura paginada e intentos
de extraer claves o inyectar instrucciones desde un documento.

Mediana: **3,49 s**; p95: **8,13 s**; máximo: **8,35 s**. Incluye la petición de chat
Moodle y sus llamadas al RAG; excluye el inicio de sesión y la navegación entre pantallas.
Los cursos temporales de paginación se eliminan al finalizar. El campus queda con nueve
cursos y trece actividades de entrega. Las notas 85 y 92 se guardan mediante la API
nativa de tareas, manteniendo coherencia con el libro y sin enviar notificaciones.

## Evaluación documental

Se evaluaron 41 consultas secuenciales sobre once documentos institucionales: 36 positivas
con hechos y documento esperado, y cinco fuera de cobertura. El generador conserva las
preguntas y el informe completo en [evaluation-deepseek-results.json](../rag-service/docs/evaluation-deepseek-results.json).

| Métrica | Resultado |
| --- | --- |
| Acierto automático en positivas | 35/36 (97,22 %) |
| Abstención en negativas | 5/5 (100 %) |
| Documento esperado citado en positivas | 36/36 |
| Respuestas sin error HTTP | 41/41 |
| Mediana | 2,629 s |
| Media | 2,666 s |
| Percentil 95, rango más próximo | 3,016 s |
| Máximo | 3,081 s |
| Duración acumulada | 109,301 s |
| Solicitudes por segundo en ejecución secuencial | 0,375 |

El criterio previo exige al menos 80 % de positivas y todas las abstenciones; se cumple.
P19 es un falso negativo del comparador literal: la respuesta «La rectificación del nombre
en un documento es gratuita y tarda dos días hábiles» cita el procedimiento correcto,
pero el caso reconoce «gratuito», «gratis» o «sin costo», no el femenino «gratuita».
Se conservó el resultado automático original. La revisión de las 36 respuestas contra sus
fuentes no identificó errores factuales en esta muestra; no es una evaluación independiente.

Las mediciones incluyen HTTP local, embeddings y generación remotos para el endpoint RAG.
No son una prueba de carga concurrente, de disponibilidad prolongada ni una certificación
sobre preguntas no evaluadas. El chat Moodle incluye interpretación, autorización y otras
etapas, por lo que sus latencias se registran por separado.

## Reproducción y alcance

Los comandos completos están en [la guía de presentación](presentacion-asistente.md).
La navegación abre pantallas autorizadas; no guarda notas, entrega tareas ni cambia cursos
mediante el chat. Pagos personales y analítica institucional agregada quedan fuera del alcance.
Los registros históricos de otros modelos se preservan como evidencia de sus ejecuciones,
con nombres y corpus originales; no son resultados del sistema actual.
