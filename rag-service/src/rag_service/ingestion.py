from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from rag_service.constants import EMBEDDING_DIMENSIONS
from rag_service.documents import chunk_pages, extract_pdf
from rag_service.embeddings import EmbeddingProvider, validate_embedding
from rag_service.errors import AppError
from rag_service.gemini import EmbeddingRouter

if TYPE_CHECKING:
    from rag_service.config import Settings
    from rag_service.repository import Repository

DOCUMENT_KINDS = ("REGLAMENTO", "PROCEDIMIENTO", "SILABO", "GUIA", "OTRO")
DOCUMENT_SCOPES = ("institutional", "course")


def ingest(
    path: Path,
    settings: "Settings",
    repository: "Repository",
    provider: EmbeddingProvider,
    *,
    scope: str,
    course_ids: tuple[int, ...] = (),
    key: str | None = None,
    title: str | None = None,
    kind: str = "OTRO",
    force: bool = False,
) -> dict:
    started_at = datetime.now(UTC)
    key = key if key is not None else path.name
    title = title if title is not None else path.stem
    if not key.strip() or len(key) > 255 or not title.strip() or len(title) > 255:
        raise AppError(
            "invalid_metadata", "Clave y título deben contener entre 1 y 255 caracteres.",
        )
    if kind not in DOCUMENT_KINDS:
        raise AppError("invalid_kind", "El tipo de documento no es válido.")
    if scope not in DOCUMENT_SCOPES:
        raise AppError("invalid_scope", "El alcance del documento no es válido.")
    if (scope == "institutional" and course_ids) or (scope == "course" and not course_ids):
        raise AppError(
            "invalid_scope", "El alcance requiere una clasificación de cursos coherente."
        )
    if any(type(course_id) is not int or course_id < 1 for course_id in course_ids):
        raise AppError("invalid_course", "Los identificadores de curso deben ser positivos.")
    if len(set(course_ids)) != len(course_ids):
        raise AppError("invalid_course", "Los identificadores de curso están duplicados.")
    course_ids = tuple(sorted(course_ids))
    if scope == "course":
        repository.validate_course_ids(course_ids)
    pdf = extract_pdf(path, settings)
    chunks = chunk_pages(pdf.pages, settings)
    with repository.locked(key) as connection:
        existing = repository.find(connection, key)
        matches = not force and existing and (
            provider.matches(existing) if hasattr(provider, "matches") else (
                existing["modelo_embedding"] == settings.bedrock_model_id
                and existing["dimension_embedding"] == EMBEDDING_DIMENSIONS
            )
        )
        if not force and matches and all((
            existing["sha256"] == pdf.sha256,
            existing["chunk_size_chars"] == settings.chunk_size_chars,
            existing["chunk_overlap_chars"] == settings.chunk_overlap_chars,
            existing["titulo"] == title,
            existing["nombre_archivo"] == pdf.filename,
            existing["ruta_archivo"] == pdf.path,
            existing["tipo_documento"] == kind,
            existing["alcance"] == scope,
            tuple(existing["course_ids"]) == course_ids,
        )):
            return {
                "status": "unchanged", "clave": key,
                "id_documento": existing["id_documento"], "version": existing["version"],
                "total_fragmentos": len(chunks), "paginas_sin_texto": list(pdf.skipped_pages),
            }
        # Ningún dato persistente cambia hasta obtener todos los embeddings válidos.
        if isinstance(provider, EmbeddingRouter) or hasattr(provider, "embed_document"):
            batches, fallback = provider.embed_document([chunk.text for chunk in chunks])
            result = repository.save(
                connection, key, title, kind, pdf, chunks, batches[0].vectors, started_at,
                scope=scope, course_ids=course_ids, batches=batches,
            )
            return dict(result, status="indexed", fallback=fallback)
        vectors = [validate_embedding(provider.embed(chunk.text)) for chunk in chunks]
        return dict(
            repository.save(
                connection, key, title, kind, pdf, chunks, vectors, started_at,
                scope=scope, course_ids=course_ids,
            ),
            status="indexed",
        )
