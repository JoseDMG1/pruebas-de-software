# Validación de rúbrica final

La especificación aprobada está en `.scratch/cumplimiento-rubrica-final/spec.md`. Estos scripts reúnen evidencia sin sobrescribir los documentos originales.

- `functional_chat.py`: aceptación real con consultas correctas, ambiguas, erróneas, fuera de alcance, permisos y planificación. Usa fechas futuras calculadas en America/Lima.
- `load_chat.py`: diez contextos de Chromium, calentamiento y cien solicitudes. Conserva errores y latencias extremas; un fallo de calentamiento impide iniciar la fase medida. No reintenta solicitudes desde el arnés.
- `test_load_metrics.py`: verifica que solicitudes lentas y errores permanecen en el denominador de aceptación.
- `profile_providers.py`: diagnóstico acotado de latencia DNS/TCP/TLS y proveedores. Instrumentación confinada a su proceso; no cambia servidores, credenciales ni configuración global.
- `report_content.py`: definición común de requisitos, historias, riesgos y casos para evitar divergencia Word–Excel.
- `figures.py`: diagramas desde código y gráficas de resultados reales.
- `build_deliverables.py`: genera DOCX, XLSX, PPTX, guion y matriz usando las evidencias existentes. Conserva estados pendientes o fallidos.
- `audit_deliverables.py`: verifica apertura de archivos, IDs, trazabilidad, referencias y ausencia de secretos configurados. No sustituye inspección visual ni aceptación funcional.

## Dependencias

Los scripts de navegador y diagnóstico utilizan `rag-service/.venv/bin/python`. Los generadores usan un entorno separado con `requirements-docs.txt`. LibreOffice y Poppler permiten exportar y revisar los PDF.

```bash
python3 -m venv --system-site-packages /tmp/rubrica-docs-venv
/tmp/rubrica-docs-venv/bin/pip install -r dev/validation/requirements-docs.txt
```

## Límites de interpretación

El caso de carga representa diez sesiones independientes sobre dos perfiles de prueba. No son diez cuentas diferentes ni un tráfico abierto de producción. La disponibilidad es muestreo HTTP durante esa ventana, no un SLA mensual. La evaluación de IA combina hechos esperados y fuentes; no es una evaluación humana independiente.

El transporte de proveedores reutiliza conexiones HTTPS mediante `provider_http.py`, con hasta 20 conexiones y un límite de establecimiento/espera de pool de tres segundos. No cachea respuestas ni autorización; los permisos se vuelven a comprobar en cada petición. La lectura y los reintentos conservan sus límites configurados.

Consultar `informe y rúbrica/corregido/GUIA-DE-ENTREGA.md` para la secuencia de reproducción y entrega. Conservar los resultados anteriores antes de reejecutar: cada salida canónica se reemplaza.

## Campaña ampliada de rendimiento

`capacity_chat.py` ejecuta una etapa con cuentas distintas, comprobaciones mínimas del contenido, percentil 99 y telemetría de host/contenedores. Cada salida debe ser nueva: se rechaza sobrescribir evidencia. Preparar las identidades con `docker compose -f compose.moodle.yaml exec -T moodle php /opt/moodle-dev/load-users.php` y guardar el JSON de perfiles; no contiene contraseñas. Usa exclusivamente el sitio local y no modifica las cuentas originales.

`capacity_campaign.py` coordina etapas secuenciales sin solaparlas. `capacity_report.py` resume todas, conservando calibración, errores y calentamientos fallidos. El patrón opcional `--pattern spike` mantiene hasta diez cuentas durante el primer minuto, activa la población completa durante el siguiente y vuelve a diez por el resto de la etapa; las transiciones se aplican entre rondas y sus tiempos efectivos quedan en las muestras.

Pruebas del arnés: `PYTHONPATH=dev/validation rag-service/.venv/bin/pytest -q dev/validation/test_capacity_chat.py dev/validation/test_load_metrics.py`. El control semántico es un oráculo mínimo por escenario, no una revisión humana exhaustiva. El generador comparte el equipo con Moodle/RAG y sus recursos deben interpretarse conjuntamente.

### Interrupción por cuota y estado de las fases

La campaña del 29/10/2026 confirmó el límite diario de 1.000 solicitudes del proyecto para Gemini embeddings. La sostenida no terminó; pico y mezcla fallaron en calentamiento. `capacity_http.py` también permite `--mix academic` para controles sin embeddings, claramente separados de la mezcla documental. El control ejecutado fue de tres consultas y no acredita capacidad HTTP alta.

`check_embedding_quota.py --output <archivo-nuevo.json>` hace una única solicitud diagnóstica y conserva únicamente estado HTTP, identificadores de cuota y demora indicada, sin claves ni cuerpo crudo. No repetirla para intentar sortear un límite diario. Los coordinadores detienen las fases posteriores cuando la sostenida no aprueba; se conservan los intentos originales anteriores a ese refuerzo.

Ver `docs/rendimiento-ampliado-resultados.md` y el estado bloqueado de `.scratch/rendimiento-ampliado/issues/01-campana.md`. La reprueba necesita cuota suficiente disponible, salidas nuevas y selección explícita de qué ejecuciones constituyen la aceptación vigente; los fallos históricos no se borran.
