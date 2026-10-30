"""Suggest study blocks from live pending tasks and explicitly declared availability."""

from datetime import date, datetime, time, timedelta
from rag_service.academic_answers import format_due_date
from rag_service.conversation import timezone_object


def compose_week(context, plan, proposal, runtime):
    zone = timezone_object(runtime.timezone)
    now = datetime.fromtimestamp(runtime.now, zone)
    start = now.date()
    if proposal.week_start:
        start = date.fromisoformat(proposal.week_start)
        end = start + timedelta(days=6)
    elif proposal.week_offset:
        start += timedelta(days=7 - start.weekday())
        end = start + timedelta(days=6)
    else:
        end = start + timedelta(days=6 - start.weekday())
    rows = context.get("assignments")
    header = (
        f"Plan de estudio\n{format_due_date(start.isoformat())} – "
        f"{format_due_date(end.isoformat())} · {runtime.timezone} · Según Moodle"
    )
    partial = plan.has_more or not plan.complete or not isinstance(rows, list)
    parts = [header]
    if partial:
        parts.append(
            "La lectura es parcial: faltan tareas o cursos por consultar. "
            "Acota a un curso o vuelve a reintentar; cualquier propuesta es parcial."
        )
    rows = [row for row in (rows or []) if row["status"] in ("not_submitted", "draft")]
    if not rows:
        parts.append(
            "No tienes tareas pendientes."
            if not partial
            else (
                "No aparecieron pendientes en los registros consultados; "
                "faltan datos para confirmar el total."
            )
        )
        return "\n\n".join(parts)

    def deadline(row):
        return datetime.fromtimestamp(row["due_at"], zone) if row.get("due_at") else None

    def priority(row):
        explicit = next(
            (
                index
                for index, name in enumerate(proposal.priority)
                if name.casefold() == row["name"].casefold()
            ),
            len(proposal.priority),
        )
        return explicit, row.get("due_at") or 4102444800, str(row["assignment_id"])

    rows.sort(key=priority)
    overdue = [row for row in rows if deadline(row) and deadline(row) < now]
    undated = [row for row in rows if not deadline(row)]
    upcoming = [row for row in rows if deadline(row) and deadline(row) >= now]

    def description(row):
        state = "borrador sin presentar" if row["status"] == "draft" else "no entregada"
        due = format_due_date(row.get("due_date")) or "sin fecha"
        return (
            f"{row['name']} — {row['course_name']}\n  Estado: {state.capitalize()} · Entrega: {due}"
        )

    # Limit display only, not the live read; disclose omitted names.
    for label, group in [
        ("Vencidas", overdue),
        ("Próximas, incluidas entregas futuras", upcoming),
        ("Sin fecha", undated),
    ]:
        if group:
            items = [description(row) for row in group[:6]]
            parts.append(label + f" ({len(group)})\n" + "\n".join("• " + item for item in items))
            if len(group) > 6:
                parts.append(
                    f"Hay {len(group) - 6} tareas adicionales en este grupo; "
                    "pide acotar el detalle por curso."
                )
    if overdue:
        parts.append(
            "Consulta al docente si admite una entrega tardía; "
            "no puedo asegurar aceptación ni una prórroga."
        )
    if undated and not proposal.priority:
        parts.append("¿Qué prioridad das a las tareas sin fecha? Indica sus nombres.")
    if not proposal.availability and not proposal.availability_unknown:
        parts.append(
            "Ya consulté tus pendientes. ¿Qué días y horas tienes disponibles para estudiar?"
        )
        return "\n\n".join(parts)
    parts.append(
        "Esta propuesta no garantiza terminar las tareas. Los bloques son espacios disponibles, "
        "no estimaciones de esfuerzo; conserva los vencimientos de Moodle."
    )
    if proposal.availability_unknown:
        parts.append("Borrador provisional sin horarios: no has precisado disponibilidad.")
        for index, row in enumerate(upcoming[:6]):
            day = min(start + timedelta(days=index), end, deadline(row).date())
            if day < now.date():
                continue
            parts.append(
                f"• {format_due_date(day.isoformat())}: avanzar {row['name']} "
                f"({row['course_name']})."
            )
        if undated:
            parts.append("Reserva espacio para las tareas sin fecha cuando indiques su prioridad.")
        return "\n\n".join(parts)
    available = proposal.availability
    slots = []
    for delta in range((end - start).days + 1):
        day = start + timedelta(days=delta)
        if day.weekday() not in available.days:
            continue
        begin = datetime.combine(day, time(available.start_hour), zone)
        finish = datetime.combine(day, time(), zone) + timedelta(hours=available.end_hour)
        if begin >= now:
            slots.append((begin, finish))
    candidates = upcoming + (undated if proposal.priority else [])
    used = set()
    count = 0
    for begin, finish in slots:
        eligible = [
            row
            for row in candidates
            if row["assignment_id"] not in used and (not deadline(row) or finish <= deadline(row))
        ]
        if not eligible:
            continue
        row = eligible[0]
        used.add(row["assignment_id"])
        parts.append(
            f"• {format_due_date(begin.strftime('%Y-%m-%d %H:%M'))}–{finish:%H:%M}: "
            f"avanzar {row['name']} ({row['course_name']})."
        )
        count += 1
        if count >= 8:
            break
    if not count:
        parts.append(
            "No hay un bloque futuro adecuado antes de los vencimientos con ese horario. "
            "¿Puedes indicar otros días u horas?"
        )
    elif len(used) < len(candidates):
        parts.append(
            "Quedan pendientes sin un bloque asignado; ajusta disponibilidad o prioridad. "
            "Una tarea puede necesitar varios bloques."
        )
    return "\n\n".join(parts)
