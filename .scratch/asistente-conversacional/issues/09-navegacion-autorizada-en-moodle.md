# Navegación autorizada en Moodle

Status: done

## Objetivo

El asistente interpreta solicitudes de navegación y ofrece enlaces a cursos, actividades,
calificaciones y calendario conforme a los permisos efectivos de estudiantes, docentes y gestión.

## Criterios de aceptación

- Seleccionar el mínimo vencimiento futuro entre actividades pendientes autorizadas, incluidas
  prórrogas, y mostrar todos los empates con sus enlaces.
- Revisar todas las páginas necesarias antes de afirmar que es el vencimiento más próximo.
- Informar cuando no hay fechas futuras o la lectura es parcial.
- Construir destinos desde identificadores nativos de Moodle; conservar validación y escape HTML.
- Ofrecer la pantalla de calificación solo con capacidad efectiva para calificar la actividad.
- Verificar navegación mediante clic real y pruebas de permisos, empates y paginación.

## Comments

La selección temporal se resuelve en Moodle. DeepSeek interpreta el propósito y el alcance.

2026-10-22: implementado y validado. PHPUnit: 51 pruebas, 234 aserciones; la suite
RAG pasa 270 pruebas. El [recorrido de navegación](../navigation-browser.json) pasa
siete consultas reales con DeepSeek y clics sobre tareas empatadas, informe personal,
calendario, tablas de calificación, libro docente y curso accesible para dirección.
También comprueba que un alumno no recibe enlace a un curso sin acceso.
