# Contenido institucional y catálogo académico

Status: done

## Objetivo

Completar el contenido consultable de la Universidad del Valle para la presentación del asistente y
ampliar el catálogo Moodle con cursos, actividades, materiales, calendario y perfiles institucionales.

## Criterios de aceptación

- La interfaz y las fuentes presentan el servicio con identidad institucional coherente.
- El corpus cubre procesos académicos, calendario, biblioteca, bienestar, soporte, becas, integridad,
  accesibilidad e investigación.
- Los cursos tienen sílabos y actividades coherentes con el catálogo Moodle y sus matrículas.
- La evaluación automatizada comprueba hechos, procedencia documental y abstención fuera de cobertura.
- Se registran los resultados de las pruebas automatizadas y métricas de latencia del servicio.

## Comments

Implementación en curso. La aceptación integrada queda pendiente de ejecutar con los proveedores
configurados y las cuentas Moodle locales.

2026-10-22: completado con once documentos institucionales, nueve sílabos, nueve
cursos, cuatro docentes y matrículas diferenciadas para los dos estudiantes.
Zona horaria America/Lima y vencimientos sincronizados con el calendario Moodle.
La evaluación real cumple el umbral: 35/36 positivas automáticas y 5/5 abstenciones;
P19 tiene un falso negativo por concordancia de género, documentado sin modificar
el resultado. Mediana 2,629 s y p95 3,016 s. Véase
[validación](../../../docs/validacion-deepseek.md).
