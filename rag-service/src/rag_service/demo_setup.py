"""Corpus ficticio reproducible; nunca carga documentos ajenos ni llama a AWS."""

import json
import textwrap
from importlib.resources import files
from pathlib import Path

from rag_service.errors import AppError
from rag_service.ingestion import ingest
from rag_service.local_embeddings import EmbeddingRouter, OllamaEmbeddingProvider
from rag_service.query import OllamaChatProvider


def corpus():
    return json.loads(files("rag_service").joinpath("demo/corpus.json").read_text())


def make_pdf(pages):
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Count {len(pages)} /Kids [".encode()
        + b" ".join(f"{4 + i * 2} 0 R".encode() for i in range(len(pages)))
        + b"] >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    for index, page in enumerate(pages):
        content = bytearray(b"BT /F1 12 Tf 40 740 Td 18 TL\n")
        for line in textwrap.wrap(page, width=76):
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            content.extend(f"({escaped}) Tj T*\n".encode("cp1252"))
        content.extend(b"ET")
        objects.extend(
            [
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + index * 2} 0 R >>".encode(),
                f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
            ]
        )
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010} 00000 n \n".encode())
    data.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(data)


def prepare_demo(settings, repository, directory=Path("data/inbox")):
    settings = settings.model_copy(update={"embedding_backend": "ollama"})
    local = OllamaEmbeddingProvider(settings)
    embeddings = local.prepare()
    chat = OllamaChatProvider(settings).prepare()
    repository.initialize()
    directory.mkdir(parents=True, exist_ok=True)
    documents = []
    for item in corpus():
        path = directory / f"demo-s1-{item['key']}.pdf"
        expected = make_pdf(item["pages"])
        if path.exists():
            if path.read_bytes() != expected:
                raise AppError(
                    "demo_file_conflict", "Un PDF de demostración existente difiere del corpus."
                )
        else:
            with path.open("xb") as output:
                output.write(expected)
        documents.append(
            ingest(
                path,
                settings,
                repository,
                EmbeddingRouter(settings),
                key=f"demo-s1-{item['key']}",
                title=item["title"],
                kind=item["kind"],
                scope="institutional",
            )
        )
    return {
        "status": "ok",
        "embedding_model": embeddings.model,
        "chat_model": chat["model"],
        "documents": documents,
        "spaces": repository.prepare_local_index(local),
    }
