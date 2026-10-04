import logging
import time
import uuid
from typing import Literal
from importlib.resources import files

import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel

from rag_service.config import Settings, get_settings
from rag_service.observability import log_event
from rag_service.repository import Repository
from rag_service.errors import AppError
from rag_service.query import QueryRequest, QueryResponse, QueryService


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    database: Literal["ok", "unavailable"]


def create_app(settings: Settings | None = None, repository=None, query_service=None) -> FastAPI:
    settings = settings or get_settings()
    repository = repository or Repository(settings)
    application = FastAPI(title="Gestor académico RAG", version="0.1.0")
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    @application.get(
        "/health",
        response_model=HealthResponse,
        responses={503: {"model": HealthResponse}},
    )
    def health():
        start = time.monotonic()
        request_id = str(uuid.uuid4())
        try:
            available = repository.health()
        except psycopg.Error:
            available = False
        log_event(
            "health",
            "ok" if available else "unavailable",
            round((time.monotonic() - start) * 1000),
            request_id,
        )
        state = "ok" if available else "unavailable"
        payload = {"status": state, "database": state}
        return JSONResponse(payload, status_code=200 if available else 503)

    service = query_service or QueryService(settings, repository)

    @application.get("/demo", response_class=HTMLResponse)
    def demo():
        return HTMLResponse(files("rag_service").joinpath("web/demo.html").read_text())

    @application.post("/api/v1/chat/query", response_model=QueryResponse)
    def query(body: QueryRequest):
        start = time.monotonic()
        request_id = str(uuid.uuid4())
        status, code = "ok", None
        try:
            return service.ask(body.query, request_id)
        except (AppError, psycopg.Error) as exc:
            status = "error"
            if isinstance(exc, psycopg.Error):
                code, message, http_status = (
                    "database_unavailable",
                    "Base de datos no disponible.",
                    503,
                )
            else:
                code, message = exc.code, str(exc)
                http_status = {
                    "invalid_generation": 502,
                    "ollama_response": 502,
                    "invalid_embedding": 502,
                    "ollama_timeout": 504,
                    "corpus_changed": 409,
                }.get(code, 503)
            return JSONResponse(
                {"code": code, "message": message, "request_id": request_id},
                status_code=http_status,
            )
        finally:
            log_event("query", status, round((time.monotonic() - start) * 1000), request_id, code)

    return application


app = create_app()
