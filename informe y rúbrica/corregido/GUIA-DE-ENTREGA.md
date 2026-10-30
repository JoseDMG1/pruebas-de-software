# Entrega corregida — Grupo 1

Los originales permanecen en la carpeta superior. El Word y Excel corregidos son editables; el PDF corresponde al Word exportado. El PPT incluye notas del presentador y tiene un guion complementario.

## Archivos principales

- `APF1 - Pruebas de Software - Grupo 1 - corregido.docx` y `.pdf`: informe completo con requisitos, HU, riesgos, diseño actualizado, resultados y casos.
- `Tablas del informe - corregidas.xlsx`: seis hojas originales reformuladas y hojas de HU, ejecución, trazabilidad, defectos, métricas, rúbrica y términos. La hoja «06 Plan de pruebas» clasifica los 36 registros en la columna «Tipo de prueba» según su finalidad principal; no se asigna Exploratorias porque no hay planes exploratorios acreditados.
- `Sustentacion - Grupo 1.pptx` y `.pdf`: presentación; la sustentación oral requiere ensayo del equipo.
- `Guion de sustentacion.md`: recorrido y preguntas de práctica.
- `matriz-cumplimiento.md`: criterios de rúbrica, evidencia y límites; no es una nota asignada.
- `evidencias/`: copia de reportes y capturas. Los scripts están en `dev/validation/` y las evidencias de trabajo en `.scratch/cumplimiento-rubrica-final/evidencias/`.

## Rendimiento ampliado y estado actual

Ver `Rendimiento ampliado - resultados.md`, sección 6.3 del informe y hoja 11 del Excel. Hay dos planes de rendimiento con resultado FALLÓ y dos hallazgos nuevos; no se declara estabilidad aprobada. Las consultas documentales están afectadas por cuota diaria de Gemini. La evidencia inicial se conserva como histórica.

## Arranque y cuentas

Desde la raíz del repositorio:

```bash
bash dev/moodle/up.sh
```

Abrir <http://127.0.0.1:8088/local/acadassistant/index.php>. Las cuentas se indican en `docs/presentacion-asistente.md`; las contraseñas están exclusivamente en `.local/sprint2-credentials.md`. Configurar claves externas en `rag-service/.env` siguiendo `.env.example`. No incluir esos archivos sensibles en el envío.

El arranque conserva volúmenes y actualiza las fechas de las actividades preparadas. Se necesita conexión a internet para DeepSeek y Gemini.

## Reproducir validación

Ejecutar desde la raíz. No ejecutar otras pruebas con proveedores mientras se mide carga.

```bash
(cd rag-service && TEST_DATABASE_URL=postgresql://rag:rag_local_dev@localhost:55432/rag PLAYWRIGHT_BROWSERS_PATH=.cache/ms-playwright .venv/bin/pytest -q --strict-markers --require-complete)
docker compose -f compose.moodle.yaml exec -T moodle vendor/bin/phpunit --testsuite local_acadassistant_testsuite
PLAYWRIGHT_BROWSERS_PATH=rag-service/.cache/ms-playwright rag-service/.venv/bin/python dev/validation/functional_chat.py
PLAYWRIGHT_BROWSERS_PATH=rag-service/.cache/ms-playwright rag-service/.venv/bin/python dev/moodle/smoke_navigation.py
PLAYWRIGHT_BROWSERS_PATH=rag-service/.cache/ms-playwright rag-service/.venv/bin/python dev/moodle/smoke_chat_ui.py
(cd rag-service && .venv/bin/python scripts/evaluate_demo.py --output ../.scratch/cumplimiento-rubrica-final/evidencias/evaluacion-ia.json)
PLAYWRIGHT_BROWSERS_PATH=rag-service/.cache/ms-playwright rag-service/.venv/bin/python dev/validation/load_chat.py
```

Los scripts nuevos guardan reportes en `.scratch/cumplimiento-rubrica-final/evidencias/`; los scripts existentes de navegación e interfaz los guardan en `.local/`. Copiar estos últimos para reunir una nueva entrega. Conservar reportes anteriores antes de reejecutar: los archivos de salida se reemplazan.

## Reconstruir documentos

Las fuentes compartidas de tablas están en `dev/validation/report_content.py`. El generador lee los reportes reales y no convierte pendientes o fallos en aprobados.

```bash
python3 -m venv --system-site-packages /tmp/rubrica-docs-venv
/tmp/rubrica-docs-venv/bin/pip install python-docx openpyxl python-pptx matplotlib
MPLCONFIGDIR=/tmp/rubrica-mpl /tmp/rubrica-docs-venv/bin/python dev/validation/build_deliverables.py
libreoffice -env:UserInstallation=file:///tmp/rubrica-lo-profile --headless --convert-to pdf --outdir 'informe y rúbrica/corregido' 'informe y rúbrica/corregido/APF1 - Pruebas de Software - Grupo 1 - corregido.docx' 'informe y rúbrica/corregido/Sustentacion - Grupo 1.pptx'
```

## Detener conservando los datos

```bash
docker compose -f compose.moodle.yaml down
docker compose -f rag-service/compose.yaml down
```

No usar `down -v` si se quieren conservar las bases y datos preparados.
