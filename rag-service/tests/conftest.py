from types import SimpleNamespace

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--require-complete", action="store_true",
        help="Rechazar la aceptación si se omite cualquier prueba o módulo",
    )


def pytest_sessionfinish(session, exitstatus):
    if not session.config.getoption("--require-complete"):
        return
    reporter = session.config.pluginmanager.getplugin("terminalreporter")
    if reporter and reporter.stats.get("skipped"):
        reporter.write_sep("=", "Aceptación incompleta: hay pruebas o módulos omitidos")
        if exitstatus == 0:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED


@pytest.fixture
def settings():
    return SimpleNamespace(
        chunk_size_chars=2000, chunk_overlap_chars=200, max_chunks=1000,
        max_pdf_bytes=20 * 1024 * 1024, max_pdf_pages=300,
        bedrock_model_id="amazon.titan-embed-text-v2:0", aws_region="us-east-1",
        aws_profile=None, bedrock_read_timeout=30,
        embedding_backend="auto", ollama_base_url="http://localhost:11434",
        ollama_embedding_model=None, ollama_default_embedding_model="qwen3-embedding:0.6b",
        ollama_embedding_context_length=2048,
        ollama_timeout=120, ollama_pull_timeout=1800, embedding_circuit_seconds=60,
        ollama_shadow_enabled=True,
    )


def pdf_bytes(texts):
    """PDF real mínimo con tabla xref, sin dependencias de generación externas."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Count {len(texts)} /Kids ["
        .encode() + b" ".join(f"{4 + i * 2} 0 R".encode() for i in range(len(texts))) + b"] >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for index, text in enumerate(texts):
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content = f"BT /F1 12 Tf 50 700 Td ({escaped}) Tj ET".encode("ascii") if text else b""
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + index * 2} 0 R >>".encode()
        )
        objects.append(
            f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
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


@pytest.fixture
def sample_pdf(tmp_path):
    path = tmp_path / "reglamento.pdf"
    path.write_bytes(pdf_bytes([
        "Academic regulations and enrollment procedures.", "Course syllabus.",
    ]))
    return path
