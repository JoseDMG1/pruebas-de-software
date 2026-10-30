"""Bounded diagnosis of provider, DNS, TCP and TLS latency; no request secrets logged."""

import concurrent.futures
import json
import socket
import ssl
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from rag_service.config import Settings
from rag_service.conversation import InterpretationRequest
from rag_service.query import QueryService
from rag_service.repository import Repository

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".scratch/cumplimiento-rubrica-final/evidencias/perfil-proveedores.json"
local = threading.local()
events = []
lock = threading.Lock()


def timed(stage, fn):
    def wrapped(*args, **kwargs):
        start = time.monotonic()
        status = "ok"
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            status = type(exc).__name__
            raise
        finally:
            with lock:
                events.append(
                    {
                        "worker": getattr(local, "worker", 0),
                        "stage": stage,
                        "seconds": round(time.monotonic() - start, 4),
                        "status": status,
                    }
                )

    return wrapped


def main():
    settings = Settings(_env_file=ROOT / "rag-service/.env")
    service = QueryService(settings, Repository(settings))
    # Temporary instrumentation remains confined to this diagnostic process.
    socket.getaddrinfo = timed("dns", socket.getaddrinfo)
    socket.socket.connect = timed("tcp_connect", socket.socket.connect)
    ssl.SSLSocket.do_handshake = timed("tls_handshake", ssl.SSLSocket.do_handshake)
    service.chat.client.request = timed("deepseek_total", service.chat.client.request)
    service.embeddings.post = timed("gemini_embedding_total", service.embeddings.post)
    runtime = {"now": int(time.time()), "timezone": "America/Lima"}

    def run(i):
        local.worker = i + 1
        question = [
            "¿Cuál es la nota mínima aprobatoria?",
            "¿Cómo solicito orientación psicológica?",
        ][i % 2]
        start = time.monotonic()
        try:
            plan = service.interpret(
                InterpretationRequest(query=question, runtime=runtime)
            )
            answer = service.documentary_evidence(question, [], f"diagnostic-{i}")
            return {
                "worker": i + 1,
                "seconds": round(time.monotonic() - start, 3),
                "ok": bool(answer.answer),
                "intent": plan.intent,
            }
        except Exception as exc:
            return {
                "worker": i + 1,
                "seconds": round(time.monotonic() - start, 3),
                "ok": False,
                "error": type(exc).__name__,
            }

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(run, range(10)))
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Direct provider chain, not Moodle capacity",
        "results": results,
        "events": events,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    for stage in sorted({e["stage"] for e in events}):
        vals = [e["seconds"] for e in events if e["stage"] == stage]
        print(
            stage,
            "calls",
            len(vals),
            "max",
            max(vals),
            "over10s",
            sum(x > 10 for x in vals),
        )


if __name__ == "__main__":
    main()
