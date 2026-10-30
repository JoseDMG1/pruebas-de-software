# Diagnóstico de la interrupción sostenida

Señal reproducible: seis errores query/gemini_throttled en sostenida-25.json; Moodle y RAG siguieron respondiendo a salud. Hipótesis consideradas: (1) ráfaga de solicitudes por minuto, (2) agotamiento diario del proyecto, (3) saturación local o del pool.

Una única petición diagnóstica embedContent confirmó HTTP 429 y quotaId EmbedContentRequestsPerDayPerProjectPerModel-FreeTier, con quotaValue=1000. Esto identifica la cuota diaria, no un timeout local, como causa de estos seis errores. No atribuye a esa causa toda la latencia del nivel 50.

El proveedor indicó retryDelay=44173s el 29/10/2026 a las 18:43:46 UTC, aproximadamente hasta el 30/10/2026 a las 02:00 en America/Lima. Es una indicación del proveedor, no una reserva de cuota ni garantía de disponibilidad posterior. Los límites RPD se restablecen a medianoche del Pacífico según https://ai.google.dev/gemini-api/docs/rate-limits . No se cambiaron modelos, claves, facturación ni resultados para hacer pasar la prueba.

La fase sostenida NO aprobó: 225 consultas, seis errores y 161,485 s de los 900 s programados. El pico falló en calentamiento (7/25 errores; cero consultas medidas). Se detuvieron los coordinadores de cargas posteriores con interrupción de las sesiones de ejecución; no se continuó enviando carga documental. La mezcla ampliada alcanzó calentamiento: cuatro fallos de diez (tres respuestas de error y una respuesta académica parcial sin la parte documental). La calibración HTTP documental falló en su única consulta de calentamiento. Ninguna de esas fases llegó a medir carga; HTTP de 50/100 cuentas quedó pendiente.

Un control HTTP independiente de tres lecturas académicas (cursos, docentes y calendario), con una cuenta y sin embeddings, respondió correctamente. No es un resultado de capacidad concurrente.

Para cerrar la estabilidad se necesita cuota disponible suficiente para toda la muestra, repetir quince minutos con 25 cuentas y posteriormente el pico. La cuota es compartida con otras llamadas del proyecto, incluida la ingesta; reiniciar Moodle no repone ese presupuesto.
