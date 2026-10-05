# Responder confirmaciones sobre docentes sin contenido ajeno

Status: done

## Problema

El usuario pregunta por profesores de sus cursos inscritos «en este ciclo», reformula
la pregunta y pide confirmar si Carla Docente es la única. El asistente repite la
lista, añade fechas y documentación no pedidas y llega a inventar el curso Diseño 204.

## Criterios de aceptación

- La secuencia literal consulta docentes de las matrículas vigentes, sin calendario
  ni documentos por la mera expresión «este ciclo».
- Confirmación directa: sí respecto a los docentes visibles, no si hay otros docentes
  visibles; no afirmar exclusividad total con lectura incompleta o sin visibilidad.
- Ningún nombre/curso del prompt se utiliza como dato académico ni como cita PDF.
- Preguntas explícitas sobre inicio del ciclo y preguntas mixtas mantienen sus fuentes.
- Regresiones en proveedor público Moodle, endpoint protegido RAG y navegador real.

## Comments

Corrección solicitada tras el cierre de los cuatro tickets originales. No cambia
la autoridad de Moodle ni crea acceso adicional a docentes o documentos.

Verificado: 31 tests Moodle (139 assertions), 164 pruebas RAG y recorrido completo
en navegador. Revisión Standards y Spec sin hallazgos pendientes. Evidencia en
[verification.md](../verification.md#corrección-de-confirmaciones-sobre-docentes).
