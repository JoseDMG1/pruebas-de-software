# Consultar datos académicos de Moodle según permisos efectivos

Status: ready-for-agent

## Objetivo

Implementar en el plugin Moodle una fuente de solo lectura que obtenga datos académicos en vivo para la pregunta actual y aplique las capacidades efectivas de Moodle en cada curso o contexto.

## Datos del primer alcance

- Cursos accesibles de la persona.
- Actividades y fechas relevantes, incluidos vencimientos de tareas.
- Estados de entrega y calificaciones visibles para la persona.
- Eventos de calendario visibles.
- Información de otros participantes solo en contextos donde Moodle permite al usuario consultarla, como datos de calificación para un docente con las capacidades necesarias.

## Requisitos

- No usar una credencial privilegiada compartida para leer indiscriminadamente datos de personas; el plugin evalúa permisos para el usuario autenticado.
- Consultar datos en vivo, en solo lectura y en respuesta a una pregunta; no sincronizar perfiles ni crear una copia persistente de datos académicos.
- Proporcionar al RAG solo los registros pertinentes y autorizados para esa pregunta, dentro del contrato firmado del ticket 01.
- Combinar el calendario Moodle con documentos institucionales oficiales. Si discrepan, conservar ambas procedencias para que la respuesta indique la discrepancia y la referencia oficial.
- Si Moodle no ofrece un dato o no autoriza la consulta, no rellenarlo a partir de inferencias.

## Criterios de aceptación

- Un estudiante autenticado recibe sus cursos, estados de entrega y calificaciones que Moodle le muestra, pero no obtiene esos datos de otro estudiante.
- Una persona docente puede consultar entregas/calificaciones de un estudiante solo en cursos donde Moodle le concede las capacidades requeridas.
- El usuario con permisos de alcance general puede obtener únicamente los datos globales que Moodle efectivamente autoriza.
- Consultar varios cursos funciona sin un curso seleccionado; limitar la consulta a uno excluye otros cursos del contexto enviado al RAG.
- Las consultas no escriben ni modifican información en Moodle y las pruebas verifican los permisos con usuarios/roles distintos.
- La implementación se prueba contra el checkout provisional Moodle 5.3dev; la compatibilidad con la versión desplegada queda pendiente de confirmación antes del despliegue.

## Dependencias

Requiere el contrato de petición Moodle–RAG del ticket 01.
