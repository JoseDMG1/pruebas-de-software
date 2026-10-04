import json
from datetime import datetime

from rag_service.observability import log_event


def test_event_records_only_operational_metadata(caplog):
    with caplog.at_level("INFO", logger="rag_service"):
        log_event("ingest", "error", 127, "test-request", "bedrock_unavailable")
    event = json.loads(caplog.records[-1].message)
    assert set(event) == {"timestamp", "operation", "status", "elapsed_ms", "request_id", "code"}
    assert datetime.fromisoformat(event["timestamp"]).utcoffset().total_seconds() == 0
    assert event["elapsed_ms"] == 127 and event["status"] == "error"
