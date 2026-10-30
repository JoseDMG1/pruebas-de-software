"""Evaluación real reproducible con DeepSeek; no cambia las preguntas."""

import argparse
import json
import math
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


def acceptance_met(positive, positives, negative, negatives, completed, expected):
    """Final-project gate: 90% factual answers and every required abstention."""
    return (
        completed == expected
        and positives > 0
        and positive >= math.ceil(positives * 0.9)
        and negative == negatives
    )


def main():
    settings = Settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--output", type=Path, default=Path("docs/evaluation-deepseek-results.json")
    )
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
    positives = sum(not item.get("insufficient") for item in cases)
    negatives = sum(bool(item.get("insufficient")) for item in cases)
    p95_index = max(0, math.ceil(len(latencies) * 0.95) - 1)
    total_elapsed = sum(item["elapsed_seconds"] for item in results)
    summary = {
        "positive_passed": positive,
        "positive_total": positives,
        "negative_passed": negative,
        "negative_total": negatives,
        "accepted": acceptance_met(
            positive, positives, negative, negatives, len(results), len(cases)
        ),
        "minimum_positive_accuracy": 0.9,
        "requests": len(results),
        "total_elapsed_seconds": round(total_elapsed, 3),
        "requests_per_second": round(len(results) / total_elapsed, 3) if total_elapsed else 0,
        "minimum_seconds": round(latencies[0], 3),
        "median_seconds": round(statistics.median(latencies), 3),
        "mean_seconds": round(statistics.mean(latencies), 3),
        "p95_seconds": latencies[p95_index],
        "maximum_seconds": round(latencies[-1], 3),
        "scoring": "Expected facts and document keys; inspect answers for semantic correctness.",
    }
    output = {
        "complete": True,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "provider": "deepseek",
        "embedding_model": settings.gemini_embedding_model,
        "embedding_provider": "gemini",
        "chat_model": settings.deepseek_chat_model,
        "summary": summary,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
