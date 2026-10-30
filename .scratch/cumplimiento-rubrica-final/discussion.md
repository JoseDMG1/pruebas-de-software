# Corrección del informe y cumplimiento de la rúbrica final

Status: confirmed

## Fuentes

- `informe y rúbrica/Rubrica_Proyecto_Final_YYBTXP.xlsx`
- `informe y rúbrica/APF1 - Pruebas de Software - Grupo 1.docx` y su PDF
- `informe y rúbrica/Tablas del informe.xlsx`
- Implementación, pruebas y reportes del repositorio; distinguir evidencias históricas de ejecuciones nuevas.

## Acuerdos con el usuario

- Corregir el informe presentado y comprobar el proyecto frente a toda la rúbrica.
- Apuntar al nivel Excelente en todos los criterios.
- Actualizar la descripción tecnológica para reflejar el sistema real.
- Entorno de entrega: ejecución local, como el proyecto actual; no se solicita despliegue público.
- Alcance final aceptado: documentos institucionales, cursos, docentes, tareas, notas, calendario, navegación autorizada y planificación semanal. El chat consulta y orienta; las escrituras se realizan en las pantallas nativas de Moodle.
- La fecha ya está definida en el informe. El usuario pide no volver a consultarla ni usarla como decisión pendiente.
- Observación del profesor: las descripciones de la mayoría de tablas son generales, usan términos imprecisos y no permiten entender claramente lo definido. Corregir contenido y precisión, además de redacción.
- Se conservan el campus y los datos de demostración actuales. El usuario pide evitar la palabra «ficticio». Formulación propuesta: «instalación local de pruebas con datos preparados para la evaluación»; no atribuir carácter oficial o procedencia institucional real sin evidencia.
- Rendimiento: al menos 95 % de respuestas del chat completo en un máximo de 10 segundos, con 10 usuarios concurrentes. Medir el servicio RAG por separado y retirar justificadamente el límite contradictorio de 5 segundos. Son objetivos por comprobar, no resultados obtenidos.
- Calidad documental: al menos 90 % de aciertos en preguntas respondibles con las fuentes. Acierto significa respuesta correcta respaldada por la fuente correspondiente. Evaluar por separado preguntas ambiguas, erróneas y fuera de alcance.

## Criterio de redacción propuesto

Cada requisito debe identificar quién lo utiliza, qué información u operación abarca, qué respuesta o comportamiento se espera y cómo se comprueba. Explicar los términos técnicos necesarios. Evitar adjetivos sin condiciones verificables y mantener trazabilidad entre requisitos, historias, casos y resultados.

## Decisiones pendientes

- Ninguna decisión de alcance pendiente. El usuario confirmó: «confirmo».

## Plan propuesto para confirmar

1. Construir una matriz de cada criterio de nivel Excelente, su evidencia existente, brechas y verificación pendiente.
2. Corregir las seis hojas de tablas y sincronizarlas con el informe: requisitos, historias, riesgos, mitigaciones y casos completos, conservando trazabilidad y explicando términos técnicos.
3. Actualizar arquitectura y alcance al sistema local actual. Describir controles realmente implementados y distinguir propuestas de resultados; concretar disponibilidad observada durante una ventana de prueba sin prometer disponibilidad de producción.
4. Corregir las brechas del proyecto y ejecutar pruebas funcionales, autorización, sesión, evaluación IA y carga reproducible. Definir antes de medir duración, mezcla de consultas, calentamiento, errores y umbrales. Conservar resultados fallidos y documentar defectos, correcciones y repruebas.
5. Integrar evidencias y resultados reales en copias corregidas del Word, PDF y Excel, preservando los originales. Preparar PPT y guion de demostración para cubrir el criterio de exposición; el dominio oral del equipo requiere ensayo y evaluación humana.
6. Revisar consistencia final entre rúbrica, tablas, informe, código y evidencias. No declarar cumplimiento de criterios sin respaldo; señalar cualquier bloqueo externo o meta no alcanzada.

## Hallazgos en las tablas originales

- RF-02 utiliza «llega correctamente» sin resultado observable; RF-06 pide «información relacionada» sin precisar evidencia suficiente ni permisos.
- CP-005 debe precisar que el contexto se mantiene durante la sesión activa, conforme al glosario; no implica historial persistente.
- RNF-07 pide 10 consultas simultáneas sin definir carga y fallos; RNF-01 exige 95 % en 10 segundos y CP-011 pide API en 5 segundos.
- RNF-02 no define ventana de disponibilidad; RNF-03 exige HTTPS entre Moodle y RAG aunque el entorno documentado es local por HTTP.
- R02 combina similitud 0.7, acierto de 90 % y feedback no acreditado. RNF-06 usa 80 %.
- Las mitigaciones mencionan herramientas o controles que deben verificarse antes de afirmarse implementados: JMeter, ZAP, caché de respuestas, S3, dos versiones de Moodle y límite de documentos de 10 MB.
- R14 menciona documentos universitarios reales; el proyecto documenta un campus de demostración.

## Estado del trabajo

Trabajo implementado y verificado tras la confirmación del usuario. Entregables en `informe y rúbrica/corregido/`; resultados actuales en `docs/validacion-rubrica-final.md`. Se conservaron originales y ejecuciones iniciales fallidas. La exposición oral corresponde al equipo.
