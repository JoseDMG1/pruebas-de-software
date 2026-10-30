# Guion de sustentación

Tiempo sugerido: 12–15 minutos más preguntas. Repartir intervenciones según los roles del informe y ensayar.

## Diapositiva 1: Gestor Académico Virtual

Presentar integrantes y problema: localizar información y tareas sin perder permisos ni fuentes.

## Diapositiva 2: Problema y alcance

Explicar una consulta documental y otra académica. Aclarar entorno local y datos preparados.

## Diapositiva 3: Arquitectura que se evaluó

Explicar qué datos salen hacia proveedores, firma versus cifrado y por qué el modelo no concede permisos.

## Diapositiva 4: Requisitos verificables

Abrir el Excel: mostrar una HU, su requisito y su caso ejecutado. No leer todas las filas.

## Diapositiva 5: Estrategia de pruebas

Distinguir suites simuladas de inferencias reales; señalar archivos JUnit y JSON.

## Diapositiva 6: Calidad de IA

Mostrar pregunta de nota mínima y la variante errónea con 20. Explicar limitaciones del comparador de hechos.

## Diapositiva 7: Carga ampliada: condiciones

Distinguir cuentas preparadas, sesiones iniciadas y carga efectivamente medida. Excluir login/calientamiento de latencia; mantener errores en el denominador. La sostenida no completó sus quince minutos: falló por cuota diaria de Gemini. Pico, mezcla ampliada y calibración HTTP documental fallaron en calentamiento; la carga HTTP alta quedó pendiente.

## Diapositiva 8: Carga ampliada: resultados

Ver tabla completa en informe sección 6.3 y Excel hoja 11. Los niveles incompletos o fuera del objetivo no aprueban. Explicar la diferencia entre límite del servidor y límite del generador local; no extrapolar a un campus.

## Diapositiva 9: Hallazgos y estados abiertos

Conservar los fallos y distinguir las correcciones anteriores de estos hallazgos abiertos. La cuota es por proyecto/modelo; una prueba corta aprobada no certifica estabilidad.

## Diapositiva 10: Demostración técnica

Abrir sesión estudiante1; usar guion. No mostrar archivo .env ni contraseñas al proyectar.

## Diapositiva 11: Límites y decisiones

Explicar por qué el cambio de alcance es explícito en las tablas y qué sería necesario para desplegar públicamente.

## Diapositiva 12: Evidencia y conclusiones

Invitar preguntas. Ensayar: qué significa p95, cómo se autoriza, qué pasa sin fuentes y cómo se reprodujo un defecto.

## Preguntas para ensayo

- ¿Por qué 95% en 10 segundos no significa que todas respondan en ese tiempo?
- ¿Por qué una cita correcta no basta para demostrar que todos los hechos de la respuesta son correctos?
- ¿Qué diferencia hay entre firma y cifrado?
- ¿Cómo se impide que un estudiante vea las notas de otro?
- ¿Qué se conserva y qué se borra al terminar la sesión?
- ¿Por qué los resultados locales no demuestran capacidad de producción?
- ¿Qué defectos se encontraron y qué evidencia comprueba su corrección?

Si falla un proveedor en vivo, mostrar el error real y las evidencias fechadas; no presentar una captura histórica como ejecución actual.
