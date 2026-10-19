# Interfaz inmediata del chat en Moodle

Status: done

## Objetivo

Hacer el chat más claro y cercano al estilo Moodle, mostrando el mensaje del estudiante
inmediatamente al enviarlo y un estado visible mientras se prepara la respuesta.

## Criterios de aceptación

- Mensajes de estudiante y asistente se distinguen visualmente; sugerencias iniciales ayudan a empezar y rellenan el campo de pregunta.
- La interfaz se adapta a pantallas pequeñas sin desbordamiento horizontal.
- Al enviar, el mensaje aparece en el chat y el botón evita envíos duplicados mientras espera.
- Un indicador accesible informa que se está preparando la respuesta; no presenta razonamiento interno del modelo.
- El flujo funciona sin JavaScript como formulario Moodle normal; sesión, permisos y respuesta siguen igual.
- Movimiento respeta `prefers-reduced-motion`; texto y fuentes siguen accesibles.

## Dependencias

Chat Moodle en `moodle/public/local/acadassistant/`.

## Estado

Implementado y verificado con navegación de escritorio y móvil, sugerencias de inicio,
mensaje optimista, estado accesible de espera y envío POST preservado. Evidencia y límites
registrados en [verification.md](../verification.md) y [ticket07-browser.json](../ticket07-browser.json).
