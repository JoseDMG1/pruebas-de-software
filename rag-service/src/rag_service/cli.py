import argparse
import json
import logging
import sys
import time
import uuid
from pathlib import Path

import psycopg
from pydantic import ValidationError

from rag_service.config import Settings
from rag_service.errors import AppError
from rag_service.gemini import EmbeddingRouter, GeminiEmbeddingProvider
from rag_service.ingestion import DOCUMENT_KINDS, ingest
from rag_service.observability import log_event
from rag_service.repository import Repository
from rag_service.query import QueryService, DeepSeekChatProvider
from rag_service.demo_setup import prepare_demo


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Administración local de la base documental RAG")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db", help="Inicializar el esquema versionado con pgvector")
    upload = commands.add_parser("ingest", help="Procesar y guardar un PDF")
    upload.add_argument("pdf", type=Path)
    upload.add_argument("--key", help="Clave estable; por defecto, el nombre del archivo")
    upload.add_argument("--title", help="Título; por defecto, el nombre sin extensión")
    upload.add_argument("--kind", choices=DOCUMENT_KINDS, default="OTRO")
    upload.add_argument("--scope", choices=("institutional", "course"), required=True)
    upload.add_argument("--course-id", type=int, action="append", default=[])
    upload.add_argument("--force", action="store_true", help="Reindexar aunque no haya cambios")
    sync = commands.add_parser(
        "sync-courses", help="Actualizar cursos válidos desde un catálogo exportado por Moodle"
    )
    sync.add_argument("catalog", type=Path, help="JSON Moodle con la propiedad course_ids")
    commands.add_parser("list", help="Listar documentos indexados y número de fragmentos")
    remove = commands.add_parser("delete", help="Eliminar un documento y todos sus fragmentos")
    remove.add_argument("key", help="Clave exacta del documento")
    smoke = commands.add_parser("check-providers", aliases=["check-gemini"],
                                help="Probar chat DeepSeek y embeddings Gemini")
    smoke.add_argument("--text", default="Reglamento académico universitario.")
    commands.add_parser("prepare-deepseek", help="Validar conexión y salida JSON de DeepSeek")
    commands.add_parser("prepare-gemini", help="Validar embeddings Gemini y chat DeepSeek")
    commands.add_parser("prepare-gemini-index", help="Indexar el corpus con embeddings Gemini")
    commands.add_parser("index-status", help="Ver cobertura por proveedor/modelo/revisión")
    question = commands.add_parser("ask", help="Preguntar al prototipo RAG local")
    question.add_argument("query")
    demo = commands.add_parser(
        "prepare-demo", help="Preparar DeepSeek, embeddings Gemini y documentos institucionales"
    )
    demo.add_argument("--directory", type=Path, default=Path("data/inbox"))
    return root


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    start = time.monotonic()
    request_id = str(uuid.uuid4())
    status = "ok"
    code = None
    try:
        settings = Settings()
        repository = Repository(settings)
        if args.command == "init-db":
            repository.initialize()
            result = {"status": "ok", "schema_version": 4}
        elif args.command == "sync-courses":
            try:
                catalog = json.loads(args.catalog.read_text())
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise AppError(
                    "invalid_course_catalog", "No se pudo leer el catálogo Moodle."
                ) from exc
            if (
                not isinstance(catalog, dict)
                or set(catalog) != {"course_ids"}
                or not isinstance(catalog["course_ids"], list)
            ):
                raise AppError(
                    "invalid_course_catalog", "El catálogo debe contener solo course_ids."
                )
            synced = repository.sync_course_catalog(catalog["course_ids"])
            result = {"status": "ok", "courses_synced": synced}
        elif args.command == "ingest":
            result = ingest(
                args.pdf,
                settings,
                repository,
                EmbeddingRouter(settings),
                key=args.key,
                title=args.title,
                kind=args.kind,
                scope=args.scope,
                course_ids=tuple(args.course_id),
                force=args.force,
            )
        elif args.command == "ask":
            result = QueryService(settings, repository).ask(args.query, request_id).model_dump()
        elif args.command == "prepare-deepseek":
            result = DeepSeekChatProvider(settings).prepare()
        elif args.command in {"prepare-gemini", "check-gemini", "check-providers"}:
            from dataclasses import asdict

            embeddings = GeminiEmbeddingProvider(settings).embed_query(
                getattr(args, "text", "Reglamento académico universitario.")
            )
            chat = DeepSeekChatProvider(settings).prepare()
            result = {
                "status": "ok", "chat_provider": "deepseek", "chat_model": chat["model"],
                "embedding_provider": "gemini",
                "embedding": asdict(embeddings.space),
            }
        elif args.command == "prepare-demo":
            result = prepare_demo(settings, repository, args.directory)
        elif args.command == "prepare-gemini-index":
            result = {"spaces": repository.prepare_embedding_index(
                GeminiEmbeddingProvider(settings),
            )}
        elif args.command == "index-status":
            result = {"spaces": repository.index_status()}
        elif args.command == "list":
            result = {"documents": repository.list_documents()}
        elif args.command == "delete":
            if not args.key.strip():
                raise AppError("invalid_key", "La clave no puede estar vacía.")
            if not repository.delete(args.key):
                raise AppError("not_found", "No existe un documento con esa clave.")
            result = {"status": "deleted", "clave": args.key}
        else:
            raise AppError("invalid_command", "El comando no está disponible.")
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (AppError, psycopg.Error, ValidationError) as exc:
        status = "error"
        if isinstance(exc, AppError):
            code, message = exc.code, str(exc)
        elif isinstance(exc, ValidationError):
            code = "invalid_query" if args.command == "ask" else "invalid_configuration"
            message = (
                "La pregunta es inválida."
                if args.command == "ask"
                else ("La configuración del servicio es inválida.")
            )
        else:
            code = "database_unavailable"
            message = "No se pudo completar la operación en PostgreSQL. Revise conexión y esquema."
        print(json.dumps({"code": code, "message": message}, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        log_event(args.command, status, round((time.monotonic() - start) * 1000), request_id, code)


if __name__ == "__main__":
    raise SystemExit(main())
