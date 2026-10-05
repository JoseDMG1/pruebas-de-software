from datetime import datetime
from zoneinfo import ZoneInfo

from rag_service.academic_answers import AcademicPlan
from rag_service.conversation import ConversationPlan, Runtime
from rag_service.weekly_plan import compose_week


def stamp(value):
    return int(datetime.fromisoformat(value).replace(tzinfo=ZoneInfo("America/Lima")).timestamp())


def task(name, due, status="not_submitted"):
    return {
        "assignment_id": name,
        "name": name,
        "course_name": "Seminario",
        "status": status,
        "due_at": stamp(due) if due else None,
        "due_date": due,
    }


def render(rows, **options):
    plan_options = options.pop("plan_options", {})
    now = options.pop("now", "2026-10-05T12:00")
    return compose_week(
        {"assignments": rows},
        AcademicPlan(categories=["assignments"], **plan_options),
        ConversationPlan(intent="weekly_plan", categories=["assignments"], **options),
        Runtime(now=stamp(now), timezone="America/Lima"),
    )


def test_reads_pending_before_requesting_availability_and_never_invents_tasks():
    answer = render([task("Ensayo", "2026-10-08T17:00")])
    assert "Ensayo" in answer and "días y horas" in answer
    assert "2026-10-05" in answer and "2026-10-11" in answer
    assert "No tienes tareas pendientes" in render([])
    assert "No tienes tareas pendientes" not in render([], plan_options={"complete": False})


def test_sunday_extension_draft_undated_and_overdue_remain_distinct():
    rows = [
        task("Extensión", "2026-10-12T17:00", "draft"),
        task("Atrasada", "2026-10-10T10:00"),
        task("Sin plazo", None),
        task("Ya entregada", "2026-10-12T12:00", "submitted"),
    ]
    answer = render(rows, now="2026-10-11T12:00", availability_unknown=True)
    assert "2026-10-11 al 2026-10-11" in answer
    assert "Extensión" in answer and "2026-10-12" in answer and "borrador" in answer
    assert "Vencidas" in answer and "Sin fecha" in answer and "prioridad" in answer
    assert "Ya entregada" not in answer
    assert "no garantiza" in answer


def test_plan_uses_declared_slots_and_flags_partial_without_changing_deadlines():
    answer = render(
        [task("Ensayo", "2026-10-08T17:00")],
        availability={"days": [1, 3], "start_hour": 14, "end_hour": 16},
        plan_options={"has_more": True},
    )
    assert "2026-10-06 14:00–16:00" in answer
    assert "2026-10-08T17:00" in answer
    assert "parcial" in answer and "reintentar" in answer
    next_week = render([], week_offset=1)
    assert "2026-10-12 al 2026-10-18" in next_week


def test_fixed_moodle_timezone_and_explicit_week_are_trusted():
    answer = compose_week(
        {"assignments": []},
        AcademicPlan(categories=["assignments"]),
        ConversationPlan(intent="weekly_plan", categories=["assignments"], week_start="2026-10-19"),
        Runtime(now=stamp("2026-10-05T12:00"), timezone="-05:00"),
    )
    assert "2026-10-19 al 2026-10-25 (-05:00)" in answer
