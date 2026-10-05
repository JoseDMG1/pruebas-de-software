"""Ingest the bounded guide verified on the local Moodle checkout."""

import subprocess
from pathlib import Path

from rag_service.demo_setup import make_pdf

root = Path(__file__).resolve().parents[2]
cwd = root / "rag-service"
text = (root / "docs/portal/moodle-5.3dev-guia.md").read_text()
path = cwd / "data/inbox/moodle-5.3dev-guia.pdf"
path.parent.mkdir(parents=True, exist_ok=True)
# Strip Markdown headings; every paragraph remains literal evidence after extraction.
paragraphs = [
    part.strip().replace("\n", " ") for part in text.split("\n\n") if part.strip()
]
path.write_bytes(make_pdf(paragraphs))
subprocess.run(
    [
        str(cwd / ".venv/bin/rag"),
        "ingest",
        str(path),
        "--key",
        "portal-moodle-5.3dev",
        "--title",
        "Guía verificada Moodle 5.3dev",
        "--kind",
        "OTRO",
        "--scope",
        "institutional",
    ],
    cwd=cwd,
    check=True,
)
