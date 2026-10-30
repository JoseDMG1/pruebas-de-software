# Clasificar documentos y filtrar por acceso antes de recuperar

Status: ready-for-agent

## Objetivo

Extender la ingesta y el repositorio RAG para que cada documento sea institucional común o esté asociado explícitamente a uno o más cursos Moodle. El filtro de acceso debe aplicarse antes de recuperar fragmentos y generar una respuesta.

## Requisitos

- La ingesta exige un alcance explícito y, para documentos de curso, uno o más identificadores estables de curso.
- Un documento sin alcance válido no se indexa para consultas.
- Documentos institucionales comunes se pueden consultar para toda cuenta personal Moodle autenticada.
- Documentos asociados a cursos solo se consideran cuando la aserción validada autoriza esos cursos.
- El repositorio filtra por alcance en la consulta vectorial. No basta con ocultar fragmentos después de recuperar o pedir al modelo que ignore material no autorizado.
- Actualizar o eliminar un documento conserva las garantías actuales de consistencia entre documento, fragmentos e índice.

## Criterios de aceptación

- La recuperación de una persona con acceso a cursos A y B nunca devuelve fragmentos del curso C.
- Una consulta sin acceso a curso aún puede recuperar documentos institucionales comunes.
- Una aserción inválida o sin ámbito no recupera documentos institucionales o de curso a través del endpoint protegido.
- Una prueba verifica que un fragmento restringido no se incluye en el prompt del modelo ni en las fuentes de respuesta.
- La metadata de alcance sobrevive actualización, reindexación y reinicio del servicio.
- Las pruebas cubren rechazo de documentos sin clasificación y curso inexistente.

## Dependencias

Requiere el contrato de identidad y contexto del ticket 01.
