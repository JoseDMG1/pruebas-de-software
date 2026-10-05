# Contrato conversacional y operaciones permitidas

Status: done

## Objetivo

Definir esquemas estrictos de intención, solicitudes de lectura, resultados y respuestas; incluir fecha y zona horaria confiables y conservar la aserción firmada.

## Criterios de aceptación

Saludo/ayuda/confirmación/plan/fuera de ámbito diferenciados; mensajes mixtos; argumentos acotados; identidad no tomada del modelo; contratos inválidos no amplían lecturas.

## Dependencias

Ninguna. Véase [spec.md](../spec.md).

## Estado

Alcance conjunto aprobado explícitamente por el usuario. Listo para implementar
cuando se cumplan las dependencias, respetando la spec y los límites acordados.

## Comments

Contrato firmado y validación de operaciones en ambos servidores comprobados con
pruebas del endpoint protegido y cliente Moodle (RED → GREEN). Revisión final pendiente
del conjunto; la implementación continúa con el ticket 02.
