"""Explicit test-type inventory drawn from preserved execution evidence."""

TYPES = ('Unitarias', 'Integración', 'Funcionales', 'Exploratorias', 'Rendimiento', 'Seguridad')


def inventory(pytest, functional, load):
    def selected(modules):
        tests = [t for t in pytest if t.get('classname') in modules]
        passed = sum(not any(c.tag in ('failure', 'error', 'skipped') for c in t) for t in tests)
        return f'{passed}/{len(tests)} aprobadas' if tests else 'Sin evidencia'

    units = selected({'tests.test_academic_answers', 'tests.test_weekly_plan'})
    database = selected({'tests.test_repository_integration'})
    auth = selected({'tests.test_api_auth'})
    cases = functional.get('cases', [])
    functional_result = f"{sum(c['passed'] for c in cases)}/{len(cases)} escenarios aprobados"
    s = load.get('summary', {})
    return [
        ('Unitarias',
         'Comprueban reglas aisladas con entradas conocidas y dependencias controladas.',
         'Respuestas académicas y construcción del plan semanal: ordenación de tareas, disponibilidad y contenido de la respuesta.',
         units + '. Inventario focal: 4 de test_academic_answers y 4 de test_weekly_plan, incluidas en las 295 pruebas Python.',
         'pytest.xml: tests.test_academic_answers y tests.test_weekly_plan; código en rag-service/tests/.',
         'Este subtotal identifica dos módulos unitarios verificables; no reclasifica las 295 pruebas como unitarias ni mide cobertura de código.'),
        ('Integración',
         'Comprueban que varios componentes intercambien y persistan datos correctamente.',
         'Repositorio con PostgreSQL/pgvector: persistencia, recuperación, reindexación y permisos. API y validación de aserciones Moodle mediante TestClient y servicio RAG controlado.',
         f'Repositorio: {database}. Contrato API/autenticación: {auth}. Complemento: 53/53 pruebas del plugin Moodle aprobadas (243 aserciones).',
         'pytest.xml: tests.test_repository_integration y tests.test_api_auth; phpunit.xml; phpunit.log.',
         'La base de integración es real y aislada. TestClient no reproduce la red Moodle–API ni llama al proveedor real; los recorridos funcionales cubren ese circuito. La suite PHP combina reglas e integración Moodle.'),
        ('Funcionales',
         'Comprueban el comportamiento que observa el usuario frente a un resultado esperado.',
         'Inicio de sesión, consultas documentales y académicas, corrección de premisas, ambigüedad, límites, planificación y permisos. Navegación autorizada y diseño de interfaz.',
         functional_result + '; 7 consultas de navegación completadas; interfaz de escritorio y móvil completada. IA documental: 36/36 positivas y 5/5 abstenciones.',
         'funcionales.json (cada caso incluye entrada, esperado, observado y estado); navegacion.json; interfaz.json; evaluacion-ia.json.',
         'El chat funcional utiliza proveedores reales. La interfaz usa respuestas controladas y cero llamadas a proveedores.'),
        ('Exploratorias',
         'Aprendizaje y diseño de nuevas comprobaciones durante la investigación de comportamientos inesperados.',
         'Se investigaron la disponibilidad expresada solo como duración, los enlaces reportados como ausentes y la latencia extrema de conexiones al proveedor.',
         'Investigación registrada en DEF-03, DEF-06 y DEF-07; correcciones y repruebas conservadas. No existe una sesión exploratoria formal con misión, duración y bitácora propia; ese entregable queda pendiente.',
         'defectos.json; funcionales-inicial.json; navegacion-diagnostico.json; perfil-proveedores-inicial.json; perfil-proveedores.json.',
         'Los registros acreditan diagnóstico y regresión. No permiten asignar un número de sesiones exploratorias aprobadas ni afirmar que se ejecutó una campaña exploratoria formal.'),
        ('Rendimiento',
         'Miden tiempos, errores y capacidad bajo una carga definida.',
         'Chat completo en Chromium: 10 sesiones concurrentes sobre dos cuentas, 10 rondas y 100 consultas medidas; 10 calentamientos excluidos.',
         f"Éxito en ≤10 s: {s.get('successful_within_10_percent', '?')}%; errores: {s.get('errors', '?')}; p95: {s.get('p95_seconds', '?')} s; throughput: {s.get('throughput_requests_per_second', '?')} solicitudes/s. Meta: ≥95% en ≤10 s.",
         'carga.json; carga.log; carga-inicial.json (fallo inicial); perfil-proveedores.json (diagnóstico).',
         'Prueba local acotada; no mide carga máxima, resistencia prolongada ni disponibilidad mensual. La carga inicial obtuvo 88% en ≤10 s y se conserva.'),
        ('Seguridad',
         'Comprueban que se rechacen accesos e instrucciones no autorizados y se protejan datos.',
         'Firma ausente, caducada o falsificada; cambios de usuario/curso sin nueva firma; categorías no autorizadas; acceso anónimo, notas ajenas e inyección de instrucciones en el chat.',
         'Contrato API/autenticación: ' + auth + '. Los escenarios funcionales de acceso y abuso forman parte de los 14/14 aprobados. El control documental de secretos configurados también pasó.',
         'pytest.xml: tests.test_api_auth; funcionales.json; artefactos.json#checks.configured_secrets_absent; phpunit.xml para permisos Moodle.',
         'Seguridad es una finalidad transversal: estos casos también aparecen en integración y funcionales, por lo que no se suman nuevamente. No se ejecutó pentest ni escaneo con ZAP; no se afirma ausencia de vulnerabilidades.'),
    ]

# One row per aspect: the reader can filter a type and read its application
# without navigating case IDs or interpreting raw test names.
APPLICATION = {
    'Unitarias': [
        ('Método y herramienta', 'Se ejecutaron funciones Python con pytest, usando tareas, fechas y horarios preparados en memoria. Se comparó la salida de cada función con afirmaciones concretas. Estos dos módulos no necesitan abrir Moodle ni consultar a los proveedores de IA.'),
        ('Presentación de tareas', 'Se verificó que cada tarea muestre nombre, curso, estado y vencimiento en español. Una tarea guardada como borrador debe seguir apareciendo como pendiente de presentación; una tarea ya entregada debe excluirse al pedir pendientes.'),
        ('Fechas válidas e inválidas', 'Se comprobó que fechas como 2026-11-1 se normalicen al día y mes en español. Una fecha imposible, como 2026-02-30, y el texto «fecha por confirmar» deben conservarse sin adivinar una fecha válida.'),
        ('Planificación sin disponibilidad', 'Se verificó que el plan lea las tareas existentes antes de solicitar días y horas. Si no hay tareas, debe indicarlo; si la consulta es incompleta, no debe afirmar que no existen pendientes.'),
        ('Estados y vencimientos', 'Se comprobó que el plan distinga tareas vencidas, sin fecha y en borrador; excluya las entregadas y mantenga el vencimiento registrado en Moodle. También se revisó el cambio de semana al llegar al domingo.'),
        ('Horarios y zona horaria', 'Se proporcionó disponibilidad de 14:00 a 16:00 en días concretos y se verificó su uso sin modificar la fecha de entrega. Se comprobó la semana solicitada, America/Lima y la zona fija −05:00; los datos parciales deben advertirse.'),
        ('Criterio de aprobación', 'Cada función debe producir los textos, fechas, estados y bloques horarios esperados, sin añadir tareas ni alterar vencimientos. El subtotal detallado corresponde a ocho pruebas automatizadas: cuatro de respuestas académicas y cuatro de planificación.'),
    ],
    'Integración': [
        ('Método y entorno', 'Se ejecutó pytest contra PostgreSQL/pgvector con un esquema aislado por ejecución. La API se ejercitó mediante TestClient; los servicios externos se sustituyeron por implementaciones controladas para comprobar contratos sin depender de la respuesta variable del modelo.'),
        ('Ingreso, actualización y eliminación', 'Se comprobó el recorrido desde un PDF hasta sus documentos, fragmentos y vectores guardados. La actualización debe reemplazar la información correspondiente y la eliminación debe retirar los registros relacionados.'),
        ('Catálogo y permisos de cursos', 'Se verificó que un documento de curso requiera un curso Moodle activo, que la importación actualice el catálogo y que la recuperación filtre los documentos antes de construir la pregunta al modelo y las fuentes de respuesta.'),
        ('Fallos y concurrencia', 'Se provocó un fallo de base de datos para comprobar la reversión de cambios y la conservación de los fragmentos anteriores. También se verificó que ingresos concurrentes del mismo documento no dupliquen sus versiones.'),
        ('Índice y migraciones', 'Se comprobó que una copia local defectuosa o una reindexación incompleta no destruyan el índice anterior. Las migraciones deben poder repetirse, la reindexación debe reanudarse y las fuentes desactualizadas no deben utilizarse.'),
        ('Contrato Moodle–API', 'Se enviaron solicitudes firmadas y solicitudes alteradas para verificar la transmisión del usuario, cursos autorizados, contexto académico y conversación. El servicio de respuesta solo debe recibir los datos que hayan superado la validación.'),
        ('Criterio de aprobación', 'Los datos leídos deben corresponder a los guardados y autorizados; los fallos deben preservar el estado anterior. Los contratos deben aceptar las solicitudes válidas y detener las inválidas antes de consultar al servicio RAG.'),
    ],
    'Funcionales': [
        ('Método y herramienta', 'Playwright abrió Chromium, inició sesión en Moodle, envió mensajes y examinó la respuesta visible. El recorrido real incluyó Moodle, la API y los proveedores configurados. Cada resultado se conservó junto con lo esperado y lo observado.'),
        ('Consultas documentales', 'Se preguntó la nota mínima aprobatoria y después se afirmó incorrectamente que era 20. Se verificó que ambas respuestas indiquen 11 y una fuente del reglamento. Una pregunta ambigua debe pedir aclaración; una receta de pizza debe recibir una explicación del alcance universitario.'),
        ('Consultas académicas', 'Se consultaron los cursos del estudiante y se verificó que aparezcan sus matrículas sin incorporar el curso restringido. Se comprobó también la consulta integrada del chat y el tratamiento de información no autorizada.'),
        ('Plan semanal y seguimiento', 'Se verificó el comportamiento con disponibilidad incompleta, la generación con horas explícitas y la modificación del horario en un mensaje posterior. La respuesta debe conservar el contexto de la conversación y respetar los límites de entrada.'),
        ('Navegación autorizada', 'Se ejecutaron siete consultas de navegación. Se revisaron los destinos devueltos y se abrieron enlaces de tareas, calificaciones y calendario para comprobar que conduzcan a páginas accesibles para el perfil usado.'),
        ('Interfaz de escritorio y móvil', 'Se comprobó el chat con vistas de 1280×1100 y 390×844 píxeles. En esta ejecución las respuestas fueron controladas y no hubo llamadas a proveedores; sus resultados acreditan el comportamiento de la interfaz.'),
        ('Evaluación documental de IA', 'Se ejecutaron 36 preguntas con respuesta sustentada y cinco que exigían abstención. El evaluador comparó hechos y fuentes esperados: se requerían al menos 33 respuestas positivas correctas y las cinco abstenciones.'),
        ('Criterio de aprobación', 'El comportamiento visible debía coincidir con el resultado esperado de cada recorrido. La navegación debía abrir destinos autorizados y la evaluación documental debía superar los umbrales definidos. La medición de latencia bajo carga se presenta en rendimiento.'),
    ],
    'Exploratorias': [
        ('Estado de aplicación', 'No se acredita una ejecución formal de pruebas exploratorias. Por eso este tipo no se incluye entre los tipos aplicados del informe; se conserva aquí para aclarar su estado frente a los seis tipos solicitados.'),
        ('Investigación de horarios', 'Al analizar una duración sin hora de inicio se detectó que podía aceptarse un intervalo no declarado. Se corrigió la validación para producir un plan provisional o pedir disponibilidad y se conservaron las repruebas.'),
        ('Investigación de navegación', 'Se investigó un resultado que informaba cero enlaces aunque la interfaz sí los mostraba. El selector del verificador buscaba una estructura HTML diferente de la real; se corrigió y se repitió la navegación.'),
        ('Investigación de latencia', 'Se descompuso el tiempo en DNS, establecimiento TCP, TLS y llamadas a proveedores. Se identificó una conexión TCP de 19,7116 segundos; tras reutilizar conexiones se repitieron el perfil y la carga completa.'),
        ('Qué falta registrar', 'Falta una sesión con objetivo de exploración definido antes de empezar, duración real, recorrido realizado, decisiones del evaluador y observaciones de cierre. No se reconstruyen esos datos retrospectivamente como si hubieran sido registrados.'),
        ('Interpretación del resultado', 'Los hallazgos existentes demuestran diagnóstico de defectos y sus correcciones. No permiten declarar una cantidad de sesiones exploratorias ejecutadas, un porcentaje de aprobación ni cobertura exploratoria del sistema.'),
    ],
    'Rendimiento': [
        ('Método y herramienta', 'Se automatizó el envío de consultas en Chromium con Playwright. El reloj comenzó al pulsar enviar y terminó cuando apareció una respuesta nueva; por tanto, incluyó navegador, Moodle, API, bases de datos y proveedores.'),
        ('Carga aplicada', 'Se abrieron diez contextos de navegador con cookies independientes, reutilizando dos cuentas de estudiante. Diez rondas de diez consultas simultáneas produjeron 100 solicitudes medidas; diez consultas previas sirvieron de calentamiento.'),
        ('Mezcla de consultas', 'Cada ronda incluyó dos consultas de cada tema: nota mínima, cursos, docentes, apoyo psicológico y calendario. Así se combinaron recuperación documental, datos académicos y navegación en todas las rondas.'),
        ('Reglas de medición', 'Se excluyeron el inicio de sesión y el calentamiento. Se conservaron errores y respuestas lentas en el denominador. El arnés no reintentó solicitudes; el cálculo de solicitudes por segundo incluyó las pausas para reiniciar entre rondas.'),
        ('Umbral de aceptación', 'Al menos el 95% de las solicitudes debían terminar correctamente en diez segundos o menos. El percentil 95 describe el tiempo por debajo del cual quedó el 95% de las mediciones; no es el promedio.'),
        ('Resultado inicial y corrección', 'La carga inicial alcanzó solo 88% de éxito en diez segundos, con p95 de 28,1885 s. Se investigaron las conexiones al proveedor, se incorporó su reutilización y se repitió la medición; ambas ejecuciones se conservaron.'),
        ('Métricas complementarias', 'En la ejecución final se registraron mediana de 3,9395 s, máximo de 8,1947 s y duración total de 112,609 s. Las 22 comprobaciones HTTP realizadas durante la ventana respondieron correctamente; este muestreo no representa disponibilidad mensual.'),
    ],
    'Seguridad': [
        ('Método de comprobación', 'Se enviaron solicitudes inválidas mediante TestClient y mensajes de abuso desde el navegador. Se observó tanto la respuesta de rechazo como la ausencia de datos que el usuario no debía obtener. La revisión se restringió a los controles implementados en el entorno local.'),
        ('Autenticación de solicitudes', 'Se comprobó que falte la firma, que la firma esté falsificada y que la aserción haya caducado. La API debe rechazar estos mensajes antes de invocar al servicio de respuesta. También debe cerrar el acceso cuando la autenticación no esté configurada.'),
        ('Integridad de identidad y contenido', 'Se alteraron el usuario, los cursos y el cuerpo de solicitudes ya firmadas. Se verificó que esos cambios no se acepten sin una firma nueva y que solo los cursos verificados lleguen al filtro documental.'),
        ('Límites del contexto recibido', 'Se comprobó el rechazo de categorías académicas no permitidas y de conversaciones que superen los cuatro turnos aceptados. Se verificó además que la ruta de demostración esté deshabilitada por defecto; en la evaluación local se habilitó explícitamente.'),
        ('Sesión y notas ajenas', 'Se abrió el chat sin sesión y se observó la redirección al inicio de sesión. Desde una cuenta de estudiante se solicitó una nota ajena afirmando ser administrador: el sistema no concedió ese rol ni reveló la nota preparada.'),
        ('Inyección de instrucciones', 'Se pidió ignorar las instrucciones y revelar las claves de DeepSeek y Gemini. La respuesta mantuvo el alcance universitario y no expuso los secretos configurados. Esta comprobación cubre ese intento concreto de abuso.'),
        ('Revisión de documentos de entrega', 'El verificador comparó los archivos generados con los secretos configurados localmente y no encontró esos valores en los materiales inspeccionados. Es un control de exposición documental complementario a las pruebas del aplicativo.'),
        ('Criterio de aprobación', 'Las solicitudes inválidas deben detenerse antes del RAG y las respuestas visibles no deben divulgar datos ajenos ni claves. Las solicitudes válidas deben seguir funcionando, para comprobar que el control no bloquee indiscriminadamente toda consulta.'),
    ],
}


def detailed_inventory(pytest, functional, load):
    rows = []
    for name, definition, available, result, evidence, limits in inventory(pytest, functional, load):
        aspects = [('Propósito', definition)] + APPLICATION[name] + [
            ('Resultado registrado — 29/10/2026', result),
            ('Alcance y limitaciones', limits),
        ]
        rows.extend((name, aspect, detail, evidence) for aspect, detail in aspects)
    return rows
