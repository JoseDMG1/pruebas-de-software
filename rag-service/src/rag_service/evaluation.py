"""Evaluación real reproducible; no cambia las preguntas ni llama a AWS."""

import argparse
import json
import re
import statistics
import time
import unicodedata
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from rag_service.config import Settings


def normalize(text):
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(char)
    )


def score(case, result):
    if case.get("insufficient"):
        return result.get("insufficient_context") is True and result.get("sources") == []
    answer = normalize(result.get("answer", ""))
    expected = "demo-s1-" + case["key"]
    return (
        result.get("insufficient_context") is False
        and any(source.get("key") == expected for source in result.get("sources", []))
        and all(
            any(contains_fact(answer, option) for option in alternatives)
            for alternatives in case["facts"]
        )
    )


def contains_fact(answer, option):
    option = normalize(option)
    if len(option) <= 4 or option.isdigit():
        return re.search(r"(?<!\w)" + re.escape(option) + r"(?!\w)", answer) is not None
    return option in answer


def main():
    settings = Settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=Path("docs/evaluation-results.json"))
    args = parser.parse_args()
    cases = json.loads(files("rag_service").joinpath("demo/evaluation.json").read_text())
    results = []
    for case in cases:
        start = time.monotonic()
        request = Request(
            args.base_url.rstrip("/") + "/api/v1/demo/chat/query",
            data=json.dumps({"query": case["query"]}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=150) as response:
                result = json.load(response)
            passed = score(case, result)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            result = {"error": type(exc).__name__}
            if isinstance(exc, HTTPError):
                result["http_status"] = exc.code
                try:
                    result["details"] = json.load(exc)
                except ValueError:
                    pass
            passed = False
        elapsed = round(time.monotonic() - start, 3)
        results.append(
            {"case": case, "passed": passed, "elapsed_seconds": elapsed, "response": result}
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps({"complete": False, "results": results}, ensure_ascii=False, indent=2) + "\n"
        )
        print(f"{case['id']}: {'PASS' if passed else 'FAIL'} ({elapsed}s)", flush=True)
        if not passed:
            print(json.dumps(result, ensure_ascii=False), flush=True)
    positive = sum(item["passed"] for item in results if not item["case"].get("insufficient"))
    negative = sum(item["passed"] for item in results if item["case"].get("insufficient"))
    latencies = sorted(item["elapsed_seconds"] for item in results)
    summary = {
        "positive_passed": positive,
        "positive_total": 20,
        "negative_passed": negative,
        "negative_total": 5,
        "accepted": len(results) == 25 and positive >= 16 and negative == 5,
        "median_seconds": round(statistics.median(latencies), 3),
        "p95_seconds": latencies[23],
        "scoring": "Expected facts and document keys; inspect answers for semantic correctness.",
    }
    output = {
        "complete": True,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "provider": "ollama",
        "embedding_model": settings.ollama_embedding_model,
        "chat_model": settings.ollama_chat_model,
        "summary": summary,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
