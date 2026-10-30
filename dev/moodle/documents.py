"""Add course syllabi and learning materials to the Moodle academic catalog."""
import json
import subprocess
from pathlib import Path

from rag_service.demo_setup import make_pdf

root = Path(__file__).resolve().parents[2]
fixtures = json.loads((root / ".local/moodle-fixtures.json").read_text())
catalog = root / ".local/course-catalog.json"
rag = root / "rag-service/.venv/bin/rag"
cwd = root / "rag-service"
subprocess.run([str(rag), "sync-courses", str(catalog)], cwd=cwd, check=True)
course_documents = {
    "ALG101": [
        "Guía de actividades de Algebra 101. La tutoría se realiza los martes a las 16:00. Código de tutoría ALG-TUTOR-16.",
        "Sílabo de Algebra 101. Unidad 1: ecuaciones lineales y sistemas. Unidad 2: funciones y gráficas. Unidad 3: polinomios. La evaluación combina prácticas semanales y un proyecto de modelado; el aula Moodle contiene las fechas vigentes.",
    ],
    "BIO102": [
        "Guía de laboratorio de Biologia 102. El informe debe incluir hipótesis, metodología y resultados. Código de laboratorio BIO-LAB-85.",
        "Sílabo de Biologia 102. El curso estudia células, genética y ecología. Para ingresar al laboratorio se requiere mandil y seguir las indicaciones de seguridad publicadas por la docente. Las muestras de práctica no se consumen ni se retiran del laboratorio.",
    ],
    "RES103": [
        "Guía de proyecto de Metodología de Investigación 103. El código de acceso a sus materiales es INV-MET-2026.",
        "Sílabo de Metodología de Investigación 103. El curso aborda formulación de problemas, diseño metodológico y análisis de fuentes. Los materiales están disponibles para estudiantes matriculados en Moodle.",
    ],
    "PROG104": [
        "Guía de laboratorio de Programacion 104. La práctica de algoritmos usa Python y evalúa descomposición del problema, corrección y pruebas. Código PROG-PY-104.",
        "Sílabo de Programacion 104. Unidades: algoritmos, estructuras de datos, pruebas automatizadas y control de versiones. El proyecto integrador se entrega en Moodle como archivo comprimido con README y código fuente. No incluir claves ni datos personales en el repositorio.",
    ],
    "COM105": [
        "Guía de escritura de Comunicacion Academica 105. La reseña crítica identifica la tesis, sustenta una evaluación propia y cita sus fuentes. Código COM-GUIA-105.",
        "Sílabo de Comunicacion Academica 105. El curso desarrolla lectura crítica, argumentación y redacción académica. La ficha de lectura es individual; la revisión entre pares es formativa y no reemplaza la entrega final en Moodle.",
    ],
    "EST106": [
        "Guía de práctica de Estadistica 106. El análisis descriptivo incluye una tabla, un gráfico pertinente y una interpretación. Código EST-DATOS-106.",
        "Sílabo de Estadistica 106. Unidades: estadística descriptiva, probabilidad, distribuciones y muestreo. Los conjuntos de datos de las prácticas no contienen información personal.",
    ],
    "FIS107": [
        "Guía de laboratorio de Fisica General 107. El informe de movimiento declara unidades, incertidumbre, procedimiento y conclusión. Código FIS-MOV-107.",
        "Sílabo de Fisica General 107. Unidades: cinemática, dinámica, energía y medición experimental. Las prácticas requieren supervisión y el equipo indicado en la guía del laboratorio.",
    ],
    "ING108": [
        "Guía de presentación de Ingles Academico 108. La exposición dura entre cuatro y seis minutos e incluye una diapositiva final con fuentes. Código ENG-SPEAK-108.",
        "Sílabo de Ingles Academico 108. El curso practica comprensión de textos, escritura y presentaciones breves. La bitácora semanal registra vocabulario y reflexión; no se califica por revelar información privada.",
    ],
    "DIS109": [
        "Guía de taller de Diseno Digital 109. El prototipo de interfaz incluye las decisiones de accesibilidad y una captura del flujo principal. Código DIS-UX-109.",
        "Sílabo de Diseno Digital 109. Unidades: investigación con usuarios, jerarquía visual, prototipos y evaluación de usabilidad. Los ejercicios no deben recolectar datos personales sin autorización.",
    ],
}
for shortname, pages in course_documents.items():
    path = cwd / "data/inbox" / f"sprint2-{shortname}.pdf"
    path.write_bytes(make_pdf(pages))
    subprocess.run([
        str(rag), "ingest", str(path), "--key", f"sprint2-{shortname}",
        "--title", f"Sílabo de {shortname}", "--kind", "SILABO",
        "--scope", "course", "--course-id", str(fixtures["courses"][shortname]),
    ], cwd=cwd, check=True)
