import json
import logging
from datetime import UTC, datetime

logger = logging.getLogger("rag_service")


def log_event(
    operation: str, status: str, elapsed_ms: int, request_id: str, code: str | None = None,
):
    logger.info(json.dumps({
        "timestamp": datetime.now(UTC).isoformat(),
        "operation": operation,
        "status": status,
        "elapsed_ms": elapsed_ms,
        "request_id": request_id,
        "code": code,
    }))
