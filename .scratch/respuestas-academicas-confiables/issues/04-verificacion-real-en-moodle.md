# Verificar corrección de respuestas con Moodle y modelo local

Status: done

## Objetivo

Ampliar fixtures y pruebas de contratos/permisos; verificar preguntas y seguimientos desde el navegador con el modelo real. Registrar resultados y limitaciones sin confundir éxito HTTP con respuesta correcta.

## Criterios de aceptación

Secuencia exacta reportada y variantes; usuarios con permisos distintos; preguntas mixtas; cero pendientes; docentes; ambigüedad; listas extensas; nuevas conversaciones y expiración; evidencia de procedencia correcta.

## Dependencias

01, 02, 03. Véase ../spec.md.

## Estado

Implementado y verificado. Evidencia: [verification.md](../verification.md).

## Comments

Cerrado tras 30 pruebas Moodle (112 assertions), 156 pruebas RAG y recorrido real
completo en navegador. Revisión de Standards y Spec sin hallazgos pendientes.
