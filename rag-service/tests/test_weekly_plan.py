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
    assert "lunes, 5 de octubre de 2026" in answer
    assert "domingo, 11 de octubre de 2026" in answer
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
    assert "domingo, 11 de octubre de 2026" in answer
    assert (
        "Extensión" in answer and "lunes, 12 de octubre de 2026" in answer and "Borrador" in answer
    )
    assert "Vencidas" in answer and "Sin fecha" in answer and "prioridad" in answer
    assert "Ya entregada" not in answer
    assert "no garantiza" in answer


def test_plan_uses_declared_slots_and_flags_partial_without_changing_deadlines():
    answer = render(
        [task("Ensayo", "2026-10-08T17:00")],
        availability={"days": [1, 3], "start_hour": 14, "end_hour": 16},
        plan_options={"has_more": True},
    )
    assert "martes, 6 de octubre de 2026 · 14:00–16:00" in answer
    assert "jueves, 8 de octubre de 2026 · 17:00" in answer
    assert "parcial" in answer and "reintentar" in answer
    next_week = render([], week_offset=1)
    assert "lunes, 12 de octubre de 2026" in next_week
    assert "domingo, 18 de octubre de 2026" in next_week


def test_fixed_moodle_timezone_and_explicit_week_are_trusted():
    answer = compose_week(
        {"assignments": []},
        AcademicPlan(categories=["assignments"]),
        ConversationPlan(intent="weekly_plan", categories=["assignments"], week_start="2026-10-19"),
        Runtime(now=stamp("2026-10-05T12:00"), timezone="-05:00"),
    )
    assert "lunes, 19 de octubre de 2026" in answer
    assert "domingo, 25 de octubre de 2026 · -05:00" in answer
