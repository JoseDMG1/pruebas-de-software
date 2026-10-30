"""Run bounded, real DeepSeek checks with synthetic conversation data and a pinned Lima clock."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import time
from zoneinfo import ZoneInfo

from rag_service.academic_answers import AcademicPlan
from rag_service.config import Settings
from rag_service.conversation import InterpretationRequest
from rag_service.errors import AppError
from rag_service.query import DeepSeekChatProvider
import rag_service.deepseek as deepseek_module
from rag_service.weekly_plan import compose_week


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--model", help="Override DEEPSEEK_CHAT_MODEL for this validation run")
    parser.add_argument("--retries", type=int, choices=range(4), default=2)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    overrides = {"deepseek_chat_model": args.model} if args.model else {}
    settings = Settings(
        deepseek_timeout=args.timeout,
        deepseek_max_retries=args.retries,
        **overrides,
    )
    provider = DeepSeekChatProvider(settings)
    model_call_count = 0
    http_attempt_count = 0
    original_request = provider.client.request
    original_urlopen = deepseek_module.urlopen

    def count_model_request(method, path, data):
        nonlocal model_call_count
        model_call_count += 1
        return original_request(method, path, data)

    def count_http_attempt(request, timeout):
        nonlocal http_attempt_count
        http_attempt_count += 1
        return original_urlopen(request, timeout=timeout)

    provider.client.request = count_model_request
    deepseek_module.urlopen = count_http_attempt
    runtime = {
        "now": int(datetime(2026, 10, 19, 10, tzinfo=ZoneInfo("America/Lima")).timestamp()),
        "timezone": "America/Lima",
    }
    cases = [
        ("courses", "¿En qué cursos estoy matriculado?", {}, None),
        ("this_week", "Organiza mis tareas para esta semana", {}, ("2026-10-19", "2026-10-25")),
        ("next_week", "Organiza mis tareas para la próxima semana", {},
         ("2026-10-26", "2026-11-01")),
        ("explicit_week", "Organiza mis tareas para la semana del 2026-11-02", {},
         ("2026-11-02", "2026-11-08")),
        ("follow_up", "¿Y quiénes más?", {"topic": {
            "intent": "academic", "categories": ["teachers"],
            "scope_question": "Mis docentes en Álgebra 101",
        }}, None),
        ("topic_change", "Ahora muéstrame mis cursos", {"topic": {
            "intent": "academic", "categories": ["assignments"],
            "scope_question": "Informe en Álgebra 101", "selected_assignment_id": 42,
        }}, None),
        ("ambiguous_task", "¿Cuándo vence esa tarea?", {"topic": {
            "intent": "academic", "categories": ["assignments"],
            "scope_question": "Mis tareas pendientes de Algebra 101",
        }}, None),
        ("availability_correction", "Mejor el viernes de 15 a 18", {
            "topic": {"intent": "weekly_plan", "categories": ["assignments"],
                       "scope_question": "Mis tareas pendientes esta semana"},
            "availability": {"days": [1, 3], "start_hour": 14, "end_hour": 16},
        }, None),
    ]
    report = {"provider": "deepseek", "model": settings.deepseek_chat_model,
              "runtime": runtime, "cases": []}
    for name, question, state, dates in cases:
        result = {"name": name, "query": question}
        started = time.monotonic()
        stop = False
        calls_before = model_call_count
        attempts_before = http_attempt_count
        try:
            request = InterpretationRequest(query=question, runtime=runtime, state=state)
            plan = provider.interpret(request)
            result["generation_calls"] = model_call_count - calls_before
            result["http_attempts"] = http_attempt_count - attempts_before
            assert 1 <= result["generation_calls"] <= 2
            assert result["http_attempts"] <= 2 * (1 + args.retries)
            result["plan"] = plan.model_dump()
            if dates:
                assert plan.intent == "weekly_plan" and plan.categories == ["assignments"]
                rendered = compose_week(
                    {"assignments": []}, AcademicPlan(categories=["assignments"]),
                    plan, request.runtime,
                )
                expected = f"Plan del {dates[0]} al {dates[1]} (America/Lima)"
                assert rendered.startswith(expected), rendered
                result["interval"] = rendered.splitlines()[0]
            elif name == "follow_up":
                assert plan.categories == ["teachers"] and plan.follow_up
                assert "101" in plan.scope_question
            elif name == "ambiguous_task":
                assert plan.categories == ["assignments"] and plan.ambiguous_task
                assert plan.selected_assignment_id == 0
            elif name == "availability_correction":
                assert plan.intent == "weekly_plan" and plan.availability
                assert plan.availability.days == [4]
                assert plan.availability.start_hour == 15 and plan.availability.end_hour == 18
            else:
                assert plan.intent == "academic" and plan.categories == ["courses"]
                assert plan.course_mode == "enrolled" and not plan.selected_assignment_id
                if name == "topic_change":
                    assert not plan.follow_up and "Informe" not in plan.scope_question
            result["ok"] = True
        except AppError as error:
            result.update(ok=False, error=error.code)
            stop = error.code in {"deepseek_unavailable", "deepseek_timeout", "deepseek_throttled"}
        except (AssertionError, ValueError) as error:
            result.update(ok=False, error=type(error).__name__, detail=str(error))
        result.setdefault("generation_calls", model_call_count - calls_before)
        result.setdefault("http_attempts", http_attempt_count - attempts_before)
        result["elapsed_seconds"] = round(time.monotonic() - started, 2)
        report["cases"].append(result)
        report["complete"] = len(report["cases"]) == len(cases)
        report["pending_cases"] = [case[0] for case in cases[len(report["cases"]):]]
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if stop:
            break
    return 0 if report["complete"] and all(row["ok"] for row in report["cases"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
