# Respaldo local con Ollama — Sprint 1

El prototipo actual trabaja exclusivamente con Ollama para embeddings y respuestas.
La recuperación básica y el chat local ya forman parte del Sprint 1 ampliado. La conexión
con Moodle permanece en Sprint 2. Este documento conserva la política opcional de respaldo
Bedrock para una futura activación explícita; el modo de trabajo predeterminado es `ollama`.

## Preparación y uso

Con las dependencias instaladas y el entorno virtual activo, desde `rag-service/`:

```bash
# Apuntar al Ollama existente, sin cambiar contenedores ni modelos.
export OLLAMA_BASE_URL=http://localhost:11434
rag prepare-ollama
rag check-ollama
rag init-db
rag ingest data/inbox/reglamento.pdf --key reglamento --kind REGLAMENTO
rag list
rag index-status
```

`prepare-ollama` consulta `GET /api/tags` y `POST /api/show`. Reutiliza un modelo con capacidad
`embedding`, eligiendo el menor tamaño en disco y desempate por nombre. Para fijar la selección
entre reinicios, configurar `OLLAMA_EMBEDDING_MODEL` con el nombre y etiqueta exactos. Un modelo
solo de chat no sustituye a un modelo de embeddings. La revisión real (digest) se guarda en la base.

Si el inventario se leyó correctamente y no existe un modelo compatible, la preparación descarga
`qwen3-embedding:0.6b`, o el modelo explícitamente configurado, mediante `POST /api/pull` y hace
una prueba mínima. No elimina otros modelos. Una conexión bloqueada o un inventario inválido
no provoca descargas. Un modelo explícito ya instalado sin capacidad de embeddings se rechaza.

`check-ollama` comprueba una inferencia sin descargar. La ingesta tampoco descarga: preparar el
modelo antes de necesitarlo sin Internet. La inferencia usa `POST /api/embed` con `truncate: false`;
rechaza textos que no entren en el contexto, vectores inválidos y cambios de dimensión o digest
entre fragmentos. Las dimensiones reales se conservan, sin rellenar ni recortar vectores.

Para usar solo el modelo local, evitando inferencias de AWS:

```bash
rag ingest data/inbox/reglamento.pdf --key reglamento --backend ollama
# O configurar EMBEDDING_BACKEND=ollama en .env.
```

## Política de respaldo

`EMBEDDING_BACKEND=auto` intenta Bedrock primero, con hasta tres intentos del SDK por llamada.
Errores de conexión, timeout, indisponibilidad del servicio y cuota (`bedrock_throttled`) activan
Ollama. Si Bedrock falla a mitad del documento, sus vectores parciales se descartan y se recalculan
TODOS los fragmentos localmente antes de guardar. Nunca se mezclan ambos modelos en un lote.

Los errores de permisos, credenciales, configuración o entrada se notifican sin ocultarlos con
el respaldo. `bedrock` exige AWS y no llama a Ollama; `ollama` usa únicamente el proveedor local.
Si falla el proveedor elegido o la escritura, permanece la última versión indexada.

El circuito evita llamar a Bedrock durante 60 segundos después de un fallo transitorio. Su estado
vive en la instancia del router: una CLI nueva empieza de nuevo; no se comparte entre procesos.
Después del intervalo, la siguiente operación vuelve a probar Bedrock. Una reingesta idéntica de
un documento local conserva ese proveedor; `--force` permite intentar su regreso a Bedrock.

## Espacios e índice local

La migración `002_embedding_spaces.sql` conserva los vectores antiguos y añade `espacio_embedding`
y `fragmento_embedding`, separados por proveedor, modelo, digest y dimensiones. Bedrock sigue
usando 1024 dimensiones; Ollama puede usar otras. El campo histórico `fragmento.embedding` conserva
los vectores primarios Bedrock y queda vacío para documentos cuyo proveedor principal es Ollama.
Todo consumidor futuro debe usar `fragmento_embedding` y un único espacio compatible.

`rag init-db` aplica ambas migraciones, de forma repetible y transaccional. Para un volumen existente
es obligatorio ejecutarlo tras actualizar el servicio; el arranque de PostgreSQL aplica migraciones
solo al crear el volumen. No es necesario borrar datos ni recrear el volumen.

En modo `auto`, una ingesta correcta con Bedrock también intenta crear una copia local
(`OLLAMA_SHADOW_ENABLED=true`). Si esa copia falla, el documento Bedrock se guarda y se indica
`local_shadow_unavailable`. Para crear o reparar el índice local del corpus ya almacenado:

```bash
rag prepare-local-index
rag index-status
```

La copia se calcula desde los textos almacenados, bajo el bloqueo de cada documento, sin cambiar
su versión ni sus vectores Bedrock. Cada documento se guarda de forma atómica. Un error interrumpe
el comando; las copias completadas previamente permanecen y puede repetirse para terminar.

`index-status` muestra cobertura del corpus vigente por espacio. `listo=true` exige cubrir TODOS
los fragmentos actuales y tener al menos uno. Actualizaciones y eliminaciones borran los vectores
obsoletos en cascada; las copias que falten hacen que la cobertura deje de estar lista. Un espacio
completo de un modelo anterior no implica que el modelo siga instalado: comprobar también
`check-ollama` y el digest seleccionado. La recuperación de consultas valida ese espacio exacto
y exige cobertura completa antes de generar una respuesta.

## Docker

Reutilizar primero el servidor existente. Para el contenedor API, configurar `OLLAMA_DOCKER_BASE_URL`
con una dirección accesible, por ejemplo `http://host.docker.internal:11434` si el servidor del host
acepta esa conexión. `localhost` dentro del contenedor identifica al propio contenedor.

Si no existe un servidor, el archivo opcional crea uno con un volumen independiente:

```bash
docker compose -f compose.yaml -f compose.ollama.yaml up --build -d
# Si ya había datos, migrarlos antes de ingestar.
docker compose -f compose.yaml -f compose.ollama.yaml run --rm api rag init-db
docker compose -f compose.yaml -f compose.ollama.yaml run --rm api rag prepare-ollama
docker compose -f compose.yaml -f compose.ollama.yaml run --rm api rag check-ollama
docker compose -f compose.yaml -f compose.ollama.yaml run --rm api \
  rag ingest /data/inbox/reglamento.pdf --key reglamento --backend ollama
```

No usar ese archivo adicional si el puerto 11434 ya está ocupado por el servicio existente. El
contenedor opcional funciona en CPU; no presupone GPU. Para `auto` con AWS en Docker, añadir
`compose.aws.yaml` siguiendo la configuración de perfil y montaje de solo lectura del README.

## Configuración

| Variable | Valor inicial |
|---|---|
| `EMBEDDING_BACKEND` | `ollama`; `auto` y `bedrock` solo si se activan explícitamente |
| `OLLAMA_BASE_URL` | `http://localhost:11434` para CLI en el host |
| `OLLAMA_DOCKER_BASE_URL` | `http://host.docker.internal:11434`, consumida por Compose |
| `OLLAMA_EMBEDDING_MODEL` | `qwen3-embedding:0.6b`; vacío permite selección automática |
| `OLLAMA_EMBEDDING_CONTEXT_LENGTH` | 2048 tokens; entradas mayores se rechazan sin truncar |
| `OLLAMA_CHAT_NUM_GPU` | -1: selección automática; 0 fuerza CPU |
| `OLLAMA_DEFAULT_EMBEDDING_MODEL` | `qwen3-embedding:0.6b`, solo para preparación |
| `OLLAMA_TIMEOUT` | 120 segundos por operación HTTP |
| `OLLAMA_PULL_TIMEOUT` | 1800 segundos para descarga |
| `EMBEDDING_CIRCUIT_SECONDS` | 60; circuito por instancia del router |
| `OLLAMA_SHADOW_ENABLED` | `true`; copia auxiliar en modo `auto` |

## Validación y trabajo posterior

Las pruebas simulan inventario, descargas, inferencias y fallos; no necesitan AWS ni Ollama real.
Cubren selección, ausencia frente a falta de acceso, descarga exclusiva en preparación, digest,
dimensiones, respaldo de documento completo, errores no transitorios y conservación de datos.
Las pruebas PostgreSQL cubren migración, copias y eliminación; requieren pgvector real.

Tras habilitar el acceso, se confirmó el contenedor Ollama existente y su modelo `llama3.2:3b`,
se descargó `qwen3-embedding:0.6b` sin eliminar el anterior y se ejecutaron inferencias reales desde
el host y Docker. La ingesta y el respaldo ante `bedrock_throttled` guardaron vectores en pgvector.
La suite completa actual aprobó 127 pruebas sin omisiones. Consultar [el informe de validación](validation.md).

El chat local usa `qwen2.5:3b`, preparado mediante `rag prepare-chat` o `rag prepare-demo`.
Se conserva el modelo Llama anterior. El cambio de modelo local se validó con el mismo corpus
y las mismas preguntas; el informe recoge la evaluación fallida del modelo anterior.
La página `/demo`, `rag ask` y la API usan el mismo servicio RAG. La evaluación real del corpus se
registra en [validación](validation.md). Moodle, autenticación para despliegue y evaluación bajo
carga quedan para los siguientes sprints.

Referencias oficiales: [inventario](https://docs.ollama.com/api/tags),
[embeddings](https://docs.ollama.com/api/embed), [chat](https://docs.ollama.com/api/chat) y
[formato de consultas de Qwen](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) y
[modelo local de respuestas](https://ollama.com/library/qwen2.5:3b).
