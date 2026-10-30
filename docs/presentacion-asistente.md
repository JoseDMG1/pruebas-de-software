# Asistente académico de la Universidad del Valle

## Acceso y configuración

Abre <http://127.0.0.1:8088/local/acadassistant/index.php>. Las cuentas y contraseñas
locales están en `.local/sprint2-credentials.md` (excluido de Git).

En `rag-service/.env`:

```dotenv
DEEPSEEK_API_KEY=<clave configurada en el servidor>
DEEPSEEK_CHAT_MODEL=deepseek-flash
GEMINI_API_KEY=<clave de embeddings>
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_EMBEDDING_DIMENSIONS=768
```

DeepSeek interpreta las preguntas, propone planes semanales y redacta respuestas
documentales. Gemini calcula embeddings. Moodle autoriza los datos y construye
los enlaces desde sus registros; el modelo no determina los permisos ni inventa URLs.
La orquestación es un asistente con varias etapas y herramientas, sin agentes
independientes que se deleguen tareas entre sí.

Desde la raíz: `bash dev/moodle/up.sh`. Repetirlo conserva los volúmenes y actualiza
los materiales y actividades de presentación; las entregas se fechan respecto al día
de preparación, en `America/Lima`. No usar este generador sobre un campus con datos reales.

## Cuentas y catálogo

| Cuenta | Perfil y alcance |
| --- | --- |
| estudiante1 | Ana Torres: siete cursos, práctica entregada y calificada, pendientes con empate de vencimiento |
| estudiante2 | Luis Mendoza: cuatro cursos, laboratorio presentado y calificación 85/100 |
| docente1 | Carla Rojas: Álgebra, Biología e Investigación |
| docente2 | Diego Salinas: Programación y Estadística |
| docente3 | Valeria Núñez: Comunicación e Inglés |
| docente4 | Jorge Rivas: Física y Diseño |
| autoridad1 | Mario Salazar: dirección académica, acceso según capacidades de gestión |
| admin_udv | Administración local |

Nueve cursos con materiales, cuatro docentes y trece actividades de entrega. Once documentos institucionales:
matrícula, reglamento, trámites, calendario, biblioteca, bienestar, servicios digitales,
becas, integridad, accesibilidad e investigación. Se añaden nueve sílabos y una guía
verificada de entregas de Moodle. La interfaz y los documentos usan identidad institucional.

## Recorrido sugerido

Inicia una conversación nueva antes de cambiar de escenario.

| Perfil | Pregunta | Resultado esperado |
| --- | --- | --- |
| Estudiante 1 | Mándame a la tarea con la entrega más próxima de llegar a su fecha límite | Dos enlaces: Reseña crítica y Análisis descriptivo; ambas vencen simultáneamente |
| Estudiante 1 | Abre mis calificaciones de Programacion 104 | Informe personal de calificaciones |
| Estudiante 1 | Llévame a mi calendario de Moodle | Calendario nativo |
| Estudiante 1 | ¿Qué profesores me enseñan? | Docentes de sus matrículas vigentes |
| Estudiante 1 | Organiza mis pendientes para la próxima semana | Propuesta editable; puede indicar sus días y horas disponibles |
| Estudiante 1 | ¿Cuál es la nota mínima aprobatoria? | Regla institucional 11 con referencia documental |
| Estudiante 1 | ¿Cómo solicito orientación psicológica? | Canal de Bienestar con fuente |
| Estudiante 1 | Abre el curso Metodología de Investigación 103 | No ofrece acceso a un curso fuera de sus permisos |
| Estudiante 2 | ¿Qué calificaciones tengo en Biologia 102? | Nota propia del laboratorio |
| Docente 1 | ¿Qué calificación tiene Luis Mendoza en Biologia 102? | Nota visible según su capacidad docente |
| Docente 2 | Llévame a calificar las entregas de Programacion 104, un curso que enseño | Enlaces a las tablas de calificación |
| Docente 2 | Abre el libro de calificaciones de Programacion 104, un curso que enseño | Libro docente |
| Autoridad | Abre el curso Programacion 104 entre los cursos disponibles que puedo consultar | Enlace al curso autorizado |

Los enlaces abren pantallas nativas. Calificar, presentar una entrega o modificar un curso
requiere completar la acción dentro de Moodle. El asistente no ejecuta esas escrituras.
Las solicitudes individuales de pagos, becas o matrículas no se consultan; sí puede
explicar sus reglas documentadas. No hay consulta analítica institucional agregada.

La búsqueda de vencimiento considera fechas futuras, pendientes y prórrogas efectivas.
Revisa las páginas disponibles y devuelve todos los empates. Si alcanza el límite de
lectura, pide acotar el curso sin afirmar que encontró el mínimo global.

## Pruebas y métricas

Resultados y límites en [validacion-deepseek.md](validacion-deepseek.md).

Desde la raíz del repositorio:

```bash
# Contratos, persistencia y UI del servicio RAG; esquemas temporales aislados.
(cd rag-service && TEST_DATABASE_URL=postgresql://rag:rag_local_dev@localhost:55432/rag \
  PLAYWRIGHT_BROWSERS_PATH=.cache/ms-playwright .venv/bin/pytest -q --strict-markers --require-complete)
# Moodle usa tablas y directorio de PHPUnit separados.
docker compose -f compose.moodle.yaml exec -T moodle \
  vendor/bin/phpunit --testsuite local_acadassistant_testsuite
# Proveedor real y clics sobre destinos Moodle.
PLAYWRIGHT_BROWSERS_PATH=rag-service/.cache/ms-playwright \
  rag-service/.venv/bin/python dev/moodle/smoke_navigation.py
# Aceptación conversacional completa.
PLAYWRIGHT_BROWSERS_PATH=rag-service/.cache/ms-playwright \
  rag-service/.venv/bin/python dev/moodle/smoke_browser.py --ticket06
# Medición secuencial del RAG: 36 preguntas con fuente y 5 fuera de cobertura.
(cd rag-service && .venv/bin/python scripts/evaluate_demo.py)
```

El informe de [evaluación DeepSeek](../rag-service/docs/evaluation-deepseek-results.json)
registra respuestas, fuentes, aciertos, abstención, mediana y percentil 95.
Las latencias corresponden a solicitudes secuenciales; no estiman capacidad bajo carga concurrente.
Los reportes históricos conservan las respuestas originales y no describen el corpus actual.

Para detener ambos proyectos conservando sus datos:

```bash
docker compose -f compose.moodle.yaml down
docker compose -f rag-service/compose.yaml down
```
