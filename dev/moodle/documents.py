"""Add explicitly scoped, fictional course documents for the localhost acceptance checks."""
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
for shortname, text in {
    "ALG101": "Documento ficticio del curso Algebra 101. La tutoria de algebra se realiza los martes a las 16:00. Codigo de tutoria ALG-TUTOR-16.",
    "BIO102": "Documento ficticio del curso Biologia 102. El informe de laboratorio debe incluir hipotesis, metodologia y resultados. Codigo de laboratorio BIO-LAB-85.",
    "RES103": "Documento ficticio del curso Reservado 103, solo para sus participantes autorizados. El codigo de entrega del proyecto reservado es ORQUIDEA-73.",
}.items():
    path = cwd / "data/inbox" / f"sprint2-{shortname}.pdf"
    path.write_bytes(make_pdf([text]))
    subprocess.run([
        str(rag), "ingest", str(path), "--key", f"sprint2-{shortname}",
        "--title", f"Documento de prueba {shortname}", "--kind", "SILABO",
        "--scope", "course", "--course-id", str(fixtures["courses"][shortname]),
    ], cwd=cwd, check=True)
