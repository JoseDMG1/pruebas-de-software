# Pruebas locales de los tickets 01–05

Moodle: <http://127.0.0.1:8088/local/acadassistant/index.php>.
El sitio y los documentos son ficticios. La interfaz Moodle está en inglés; el modelo responde en español.
El enlace **Academic assistant** aparece en la barra principal al iniciar sesión con una cuenta personal.

## Cuentas y datos

Las contraseñas se guardan únicamente en `.local/sprint2-credentials.md`, excluido de Git.

| Cuenta | Acceso de prueba |
| --- | --- |
| `estudiante1` (Ana Prueba) | Algebra 101 y Biologia 102; dos tareas pendientes |
| `estudiante2` (Luis Prueba) | Biologia 102 y Reservado 103; entrega de laboratorio presentada y nota 85/100 |
| `docente1` (Carla Docente) | Docente de Biologia 102; puede consultar la nota de Luis en ese curso |
| `autoridad1` (Mario Direccion) | Rol manager con capacidades a nivel del sitio |
| `admin_sprint2` | Administración del entorno local |

Cada curso tiene un PDF propio. El documento de Reservado 103 contiene el código ficticio
`ORQUIDEA-73`, para comprobar que solo lo reciben sus participantes y las cuentas con permisos globales.
El corpus institucional común conserva los documentos ficticios de Universidad Demo del Valle.

## Recorrido de prueba

1. Entra como `estudiante1`, abre **Academic assistant** y pregunta **¿Qué tareas tengo pendientes?**.
   Debe utilizar las tareas visibles en sus dos cursos, con procedencia Moodle.
2. Pregunta **¿Y cuándo vencen?**, para comprobar el contexto temporal.
3. Pulsa **New conversation**. El transcript desaparece y el seguimiento empieza sin los turnos anteriores.
4. Pregunta **¿Cuál es la nota mínima aprobatoria en Universidad Demo del Valle?**.
   La respuesta debe citar el reglamento ficticio: 11.
5. Pregunta **¿Cuál es el código de entrega del proyecto del curso Reservado 103?**.
   `estudiante1` no debe recibir `ORQUIDEA-73`, ni fuentes del curso reservado.
6. Cierra sesión, entra como `estudiante2` y repite la pregunta del curso reservado.
   Esta cuenta sí tiene acceso al documento. El chat empieza vacío después del nuevo login.
7. Como `docente1`, pregunta **¿Qué calificación tiene Luis Prueba en Biologia 102?**.
   Debe utilizar la nota visible en Moodle (85/100).
8. Como `autoridad1`, pregunta **¿Qué cursos están disponibles?**.
   Sus capacidades efectivas permiten acceder a los tres cursos de prueba.

Para provocar la comprobación real de timeout en la siguiente petición de una cuenta de prueba,
sin esperar los 30 minutos configurados:

```bash
docker compose -f compose.moodle.yaml exec -T -u www-data moodle \
  php /opt/moodle-dev/expire-session.php estudiante1
```

Recarga el chat de esa cuenta: Moodle debe pedir iniciar sesión y no restaurar su conversación.

## Encender, detener y verificar

Desde la raíz del repositorio, con Docker, Python y el Ollama existente disponibles:

```bash
bash dev/moodle/up.sh
```

El script conserva la configuración local existente, instala o actualiza el plugin,
prepara las cuentas y sincroniza el catálogo confiable de cursos con RAG.
Reutiliza los volúmenes propios de Moodle y la base RAG existente.

```bash
# Detener Moodle sin borrar sus datos.
docker compose -f compose.moodle.yaml stop
# Verificación real en Chromium, Moodle y Ollama.
rag-service/.venv/bin/python dev/moodle/smoke_browser.py
# PHPUnit del plugin, usando el prefijo phpu_ y dataroot separado.
docker compose -f compose.moodle.yaml exec -T moodle \
  php public/admin/tool/phpunit/cli/init.php
docker compose -f compose.moodle.yaml exec -T moodle \
  vendor/bin/phpunit --testsuite local_acadassistant_testsuite
```

El reporte de navegador y las capturas se guardan bajo `.local/`, excluido de Git.
Las credenciales de servicio están en `.moodle.env` y `rag-service/.env`; ninguna se envía al navegador.
Moodle escucha solo en `127.0.0.1:8088`, su PostgreSQL en `127.0.0.1:55433` y el RAG en `127.0.0.1:8000`.
El contenedor Moodle usa la red del host Linux para que el cliente RAG siga usando una URL loopback
permitida por su contrato, sin cambiar la restricción HTTPS del cliente.

## Respuestas académicas confiables

«Qué cursos tengo», «qué materias llevo» y «en qué estoy matriculado» consultan
matrículas vigentes. «Qué cursos puedo consultar» refleja el acceso efectivo y
«qué cursos enseño» las responsabilidades docentes del curso.

«Qué tareas tengo» muestra pendientes de entrega. Puedes pedir todas las tareas
o las entregadas. Las preguntas sobre docentes devuelven nombres visibles por curso,
respetando permisos y grupos. Las cuotas personales siguen fuera de alcance.

Prueba también esta secuencia sin pulsar **New conversation**:

1. **¿Qué tareas tengo?**
2. **¿Cuánto me está costando las cuotas?**
3. **¿Cuáles son todos los nombres de mis profesores?**
4. **¿Qué cursos tengo?**
5. **¿Qué materias llevo?**

La negativa sobre cuotas no debe impedir responder profesores o cursos. Una
consulta académica utiliza procedencia Moodle y no citas de PDFs. Para combinar
fuentes, pregunta **¿Qué cursos tengo y cuál es la nota mínima aprobatoria en
Universidad Demo del Valle?**. La respuesta distingue los datos Moodle del reglamento.

Después de listar varias tareas, **¿cuándo vence esa tarea?** pide aclarar cuál;
puedes responder con el nombre de la tarea. Una lista parcial permite escribir
**continúa**, volviendo a comprobar los permisos. Nueva conversación borra ese cursor.

El smoke crea además `estudiante_lista` con 22 cursos de prueba para verificar
continuación. Usa la contraseña local de las demás cuentas.

Las respuestas académicas concretas se componen desde los registros autorizados;
la parte documental sigue usando el modelo local y puede tardar decenas de segundos.
El reporte real y capturas se guardan en `.local/`.

La suite RAG completa utiliza `rag_sprint2_tests`, una base separada del corpus demo:

```bash
TEST_DATABASE_URL=postgresql://rag:rag_local_dev@127.0.0.1:55432/rag_sprint2_tests \
  rag-service/.venv/bin/python -m pytest rag-service/tests -q --require-complete
```
