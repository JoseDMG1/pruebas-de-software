from rag_service.academic_answers import AcademicPlan, compose_academic, format_due_date


def test_pending_tasks_are_rendered_as_a_scannable_list_with_spanish_dates():
    answer = compose_academic(
        {
            "assignments": [
                {
                    "name": "Ensayo",
                    "course_name": "Historia",
                    "status": "not_submitted",
                    "due_date": "2026-10-29 16:18",
                },
                {
                    "name": "Informe",
                    "course_name": "Biología",
                    "status": "draft",
                    "due_date": "2026-11-01 09:30",
                },
            ]
        },
        AcademicPlan(categories=["assignments"]),
        "¿Qué tareas tengo pendientes?",
    )

    assert "Tareas pendientes de entrega (2)" in answer
    assert (
        "• Ensayo — Historia\n  Estado: No entregada · Entrega: jueves, 29 de octubre de "
        "2026 · 16:18" in answer
    )
    assert (
        "• Informe — Biología\n  Estado: Borrador sin presentar · Entrega: domingo, 1 de "
        "noviembre de 2026 · 09:30" in answer
    )
    assert "; vence" not in answer


def test_empty_and_filtered_task_results_remain_clear():
    answer = compose_academic(
        {
            "assignments": [
                {
                    "name": "Ensayo",
                    "course_name": "Historia",
                    "status": "submitted",
                    "due_date": "2026-10-29 16:18",
                }
            ]
        },
        AcademicPlan(categories=["assignments"], assignment_filter="pending"),
    )
    assert answer == "Según Moodle:\n\nTareas pendientes de entrega\nNo tienes tareas pendientes."


def test_unparseable_date_is_preserved_instead_of_guessed():
    assert format_due_date("fecha por confirmar") == "fecha por confirmar"
    assert format_due_date("2026-02-30 16:18") == "2026-02-30 16:18"


def test_unpadded_moodle_dates_are_normalized():
    assert format_due_date("2026-11-1 16:18") == "domingo, 1 de noviembre de 2026 · 16:18"
    assert format_due_date("2026-11-4 16:18") == "miércoles, 4 de noviembre de 2026 · 16:18"
