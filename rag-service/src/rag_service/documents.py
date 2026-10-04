import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from rag_service.errors import AppError

if TYPE_CHECKING:
    from rag_service.config import Settings


@dataclass(frozen=True)
class PageText:
    number: int
    text: str


@dataclass(frozen=True)
class ExtractedPdf:
    filename: str
    path: str
    sha256: str
    pages: tuple[PageText, ...]
    total_pages: int
    skipped_pages: tuple[int, ...]


@dataclass(frozen=True)
class Chunk:
    position: int
    page_start: int
    page_end: int
    text: str


def extract_pdf(path: Path, settings: "Settings") -> ExtractedPdf:
    if path.suffix.lower() != ".pdf":
        raise AppError("invalid_pdf", "El archivo debe tener extensión PDF.")
    try:
        # Leer una sola instantánea limita la entrada y mantiene hash/texto consistentes.
        with path.open("rb") as source:
            data = source.read(settings.max_pdf_bytes + 1)
    except OSError as exc:
        raise AppError("pdf_unreadable", "No se pudo leer el archivo PDF.") from exc
    if not data:
        raise AppError("empty_pdf", "El PDF está vacío.")
    if len(data) > settings.max_pdf_bytes:
        raise AppError("pdf_too_large", "El PDF supera el tamaño máximo permitido.")
    if not data.startswith(b"%PDF-"):
        raise AppError("invalid_pdf", "El contenido no corresponde a un PDF válido.")
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise AppError("encrypted_pdf", "El prototipo no admite PDF cifrados.")
        if len(reader.pages) > settings.max_pdf_pages:
            raise AppError("too_many_pages", "El PDF supera el número máximo de páginas.")
        pages = []
        skipped = []
        for number, page in enumerate(reader.pages, start=1):
            text = re.sub(r"\s+", " ", (page.extract_text() or "").replace("\x00", " ")).strip()
            if text:
                pages.append(PageText(number, text))
            else:
                skipped.append(number)
    except (PyPdfError, ValueError, TypeError, KeyError, IndexError, RecursionError) as exc:
        raise AppError("invalid_pdf", "No se pudo procesar el PDF; puede estar dañado.") from exc
    if not pages:
        raise AppError("no_text", "El PDF no contiene texto extraíble. Se requiere OCR.")
    return ExtractedPdf(
        filename=path.name,
        path=str(path.resolve()),
        sha256=hashlib.sha256(data).hexdigest(),
        pages=tuple(pages),
        total_pages=len(reader.pages),
        skipped_pages=tuple(skipped),
    )


def chunk_pages(pages: tuple[PageText, ...], settings: "Settings") -> list[Chunk]:
    chunks = []
    for page in pages:
        start = 0
        while start < len(page.text):
            end = min(start + settings.chunk_size_chars, len(page.text))
            if end < len(page.text):
                boundary = page.text.rfind(" ", start, end)
                if boundary > start:
                    end = boundary
            text = page.text[start:end].strip()
            if text:
                chunks.append(Chunk(len(chunks), page.number, page.number, text))
            if len(chunks) > settings.max_chunks:
                raise AppError("too_many_chunks", "El PDF genera demasiados fragmentos.")
            if end == len(page.text):
                break
            # Alinear el solapamiento a palabras sin detener el avance.
            next_start = max(start + 1, end - settings.chunk_overlap_chars)
            boundary = page.text.rfind(" ", start + 1, next_start + 1)
            start = boundary + 1 if boundary >= start + 1 else next_start
    return chunks
