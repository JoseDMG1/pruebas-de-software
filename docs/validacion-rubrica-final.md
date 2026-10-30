# Validación de la rúbrica final — 29 de octubre de 2026

La [entrega corregida](<../informe y rúbrica/corregido/GUIA-DE-ENTREGA.md>) contiene Word/PDF, Excel, PPT, guion y evidencias. Los originales se preservan. La [spec aprobada](../.scratch/cumplimiento-rubrica-final/spec.md) fija el alcance y los umbrales.

## Actualización: rendimiento ampliado

Ver [campaña ampliada](rendimiento-ampliado-resultados.md): 1.865 consultas medidas en cinco fases de navegador; 25 cuentas aprobaron la carga breve, 50 incumplieron latencia y la sostenida falló por cuota diaria de Gemini. CP-011/012 ampliados quedan fallidos (34/36 casos con aprobación de referencia); DEF-08/09 registran los hallazgos. Los resultados siguientes corresponden a la ejecución inicial y se conservan como históricos.

## Resultados comprobados — referencia inicial

| Verificación | Resultado |
|---|---|
| Suite Python completa | 295 aprobadas, ninguna omitida; un aviso de deprecación de Starlette/TestClient |
| Plugin Moodle | 53 pruebas, 243 aserciones, aprobadas |
| Aceptación de chat con proveedores reales | 14/14 comprobaciones aprobadas |
| Navegación y apertura de destinos | Siete consultas, recorrido completo |
| Interfaz controlada | Escritorio 1280×1100 y móvil 390×844; sin llamadas a IA en este test |
| Evaluación documental | 36/36 positivas y 5/5 abstenciones; objetivo ≥90% positivas |
| Casos documentados y trazados | 36/36 aprobados dentro de su alcance definido |
| Carga real | 10 sesiones independientes, 100 solicitudes; 100% exitosas en ≤10 s; cero errores |
| Latencia de carga | Mediana 3,9395 s; p95 7,3972 s; máximo 8,1947 s |
| Throughput | 0,888 solicitudes/s; incluye reinicios de conversación entre rondas |
| Disponibilidad observada | 22/22 muestras HTTP conjuntas exitosas durante la carga; no es disponibilidad mensual |

Los reportes están en `.scratch/cumplimiento-rubrica-final/evidencias/` y se copian a la entrega. La evaluación documental secuencial tiene mediana 1,751 s y p95 2,411 s; no se confunde con el chat concurrente.

## Correcciones y evidencia de fallos

- Evaluador: umbral de 80% actualizado a 90%, con pruebas del límite 32/36 frente a 33/36.
- Comparador: se admite «gratuita» sin omitir el plazo ni la fuente requeridos por P19.
- Plan semanal: una duración sin intervalo explícito no se convierte en horas inventadas. Horarios incompletos producen borrador provisional; los horarios completos conservan la semana en los seguimientos.
- Arnés funcional: se corrigieron falsos negativos de aclaración y se exige comprobar los bloques horarios, no solo la aparición de un día en una fecha de entrega.
- Navegación: selector actualizado a `a.local-acadassistant-destination`; el reporte conserva la respuesta además de los enlaces.
- Transporte de proveedores: reutilización de conexiones HTTPS, hasta 20 conexiones y timeout de establecimiento/pool de tres segundos. Las credenciales se adjuntan por petición y no se cachean respuestas ni permisos.

La carga inicial devolvió cero errores, pero solo 88% en ≤10 s y p95 28,1885 s. El perfil localizó 19,7116 s en una conexión TCP. Se conservan `carga-inicial.json`, `perfil-proveedores-inicial.json`, `funcionales-inicial.json` y las repruebas. El resultado final se obtuvo manteniendo la mezcla, diez sesiones, diez rondas y los mismos umbrales.

## Interpretación y límites

Diez contextos de Chromium reutilizan dos cuentas preparadas; no son diez personas diferentes. Se excluyen login y diez consultas de calentamiento. Se conservan todas las solicitudes medidas, incluidos errores y extremos. Las llamadas remotas y su latencia pueden variar.

El entorno permanece en localhost. HTTP interno no cifra el tráfico; firma y permisos protegen la integración. La ruta documental de evaluación local se habilita por separado y no recibe el contexto académico personal. Los proveedores externos usan HTTPS.

Los criterios técnicos y documentales cuentan con evidencia para esta entrega local. El PPT y el guion están preparados, pero el dominio oral y la nota final corresponden a la sustentación del equipo y a la evaluación del docente. La prueba de interfaz no es un estudio con participantes independientes ni los resultados certifican capacidad de producción.

## Reproducción

Ver [dev/validation/README.md](../dev/validation/README.md) y la guía incluida en la entrega. No ejecutar otras pruebas con proveedores durante la carga. Los scripts reemplazan sus salidas: conservar las ejecuciones anteriores antes de repetirlos.
