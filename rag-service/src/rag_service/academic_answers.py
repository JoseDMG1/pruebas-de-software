"""Render authorized academic facts independently of documentary generation."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt


class AcademicPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    categories: list[Literal["courses", "assignments", "grades", "calendar", "teachers"]]
    course_mode: Literal["enrolled", "accessible", "teaching"] = "enrolled"
    assignment_filter: Literal["pending", "submitted", "all"] = "pending"
    has_more: StrictBool = False
    complete: StrictBool = True
    continuing: StrictBool = False
    teacher_confirmation: StrictBool = False
    notices: list[str] = Field(default_factory=list, max_length=10)
    document_course_ids: list[StrictInt] | None = Field(default=None, max_length=500)
    document_question: str = Field(default="", max_length=1000)


def compose_academic(context: dict, plan: AcademicPlan, question: str = "") -> str:
    """Missing or malformed data fails closed; a known empty result remains a fact."""
    parts = []
    for category in plan.categories:
        if category not in context:
            continue  # A clarification can intentionally withhold an ambiguous category.
        rows = context[category]
        if not isinstance(rows, list):
            raise ValueError("Los resultados académicos deben ser listas.")
        if category == "courses":
            heading = {
                "enrolled": "Cursos con matrícula vigente",
                "accessible": "Cursos que puedes consultar",
                "teaching": "Cursos que enseñas",
            }[plan.course_mode]
            parts.append(
                heading
                + ": "
                + (
                    "; ".join(f"{row['name']} ({row['short_name']})" for row in rows)
                    if rows
                    else "no hay cursos en este resultado"
                )
                + "."
            )
        elif category == "assignments":
            heading = {
                "pending": "Tareas pendientes de entrega",
                "submitted": "Tareas entregadas",
                "all": "Tareas visibles",
            }[plan.assignment_filter]
            items = []
            for row in rows:
                status = {
                    "not_submitted": "no entregada",
                    "draft": "borrador sin presentar",
                    "submitted": "entregada",
                }.get(row["status"], row["status"])
                if plan.assignment_filter == "pending" and row["status"] == "submitted":
                    continue
                if plan.assignment_filter == "submitted" and row["status"] != "submitted":
                    continue
                due = row.get("due_date") or "sin fecha de vencimiento disponible"
                items.append(f"{row['name']} — {row['course_name']}: {status}; vence {due}")
            parts.append(
                heading
                + ": "
                + (
                    "; ".join(items)
                    if items
                    else (
                        (
                            "no hay más tareas pendientes en este resultado"
                            if plan.continuing
                            else "no tienes tareas pendientes"
                            if plan.complete
                            else "no hay tareas pendientes entre los registros consultados"
                        )
                        if plan.assignment_filter == "pending"
                        else "no hay tareas en este resultado"
                    )
                )
                + "."
            )
        elif category == "teachers":
            if plan.teacher_confirmation:
                parts.append(confirm_teacher(rows, plan, question))
                continue
            items = []
            for row in rows:
                names = ", ".join(row["names"])
                if row.get("state") == "unavailable":
                    names = "no puedo consultar los docentes con el acceso disponible"
                elif not names:
                    names = "no hay docentes asignados o visibles en este resultado"
                items.append(f"{row['course_name']}: {names}")
            parts.append(
                "Docentes por curso: "
                + ("; ".join(items) or "no hay cursos en este resultado")
                + "."
            )
        elif category == "grades":
            parts.append(
                "Calificaciones visibles: "
                + (
                    "; ".join(
                        f"{row['item_name']} — {row['course_name']}"
                        f"{(' — ' + row['participant']) if row.get('participant') else ''}"
                        f": {row['grade']}"
                        for row in rows
                    )
                    or "no hay calificaciones visibles en este resultado"
                )
                + "."
            )
        elif category == "calendar":
            parts.append(
                "Calendario Moodle: "
                + (
                    "; ".join(f"{row['name']}: {row['starts_date']}" for row in rows)
                    or "no hay eventos visibles en el intervalo consultado"
                )
                + "."
            )
    if parts and not (plan.teacher_confirmation and plan.categories == ["teachers"]):
        parts.insert(0, "Según Moodle:")
    parts.extend(plan.notices)
    if plan.has_more:
        parts.append("Esta lista es parcial. Escribe «continúa» para ver más resultados.")
    if not plan.complete:
        parts.append(
            "La consulta alcanzó el límite de cursos. Acota la pregunta a un curso; "
            "este resultado no representa todos tus datos."
        )
    return "\n".join(parts)


def confirm_teacher(rows: list, plan: AcademicPlan, question: str) -> str:
    """Confirm only a visible, complete set; unseen assignments remain unknown."""
    import unicodedata

    def normalise(text):
        return unicodedata.normalize("NFKD", text.casefold()).encode("ascii", "ignore").decode()

    names = list(dict.fromkeys(name for row in rows for name in row["names"]))
    matched = [name for name in names if normalise(name) in normalise(question)]
    populated = [row for row in rows if row["names"]]
    identities_known = all(isinstance(row.get("teacher_id"), int) and
                           not isinstance(row.get("teacher_id"), bool) and row["teacher_id"] > 0
                           for row in populated)
    identities = {row["teacher_id"] for row in populated} if identities_known else set()
    gaps = list(dict.fromkeys(row["course_name"] for row in rows
                              if not row["names"] or row.get("state") == "unavailable"))
    if not names:
        return ("No puedo confirmar quién te enseña con los datos visibles de Moodle. "
                "No ver docentes no significa que no haya docentes asignados.")
    if plan.has_more or not plan.complete:
        return ("No puedo confirmar que sea la única docente: la consulta es parcial. "
                "Según Moodle, aparecen: " + ", ".join(names) + ".")
    if len(matched) == 1 and len(names) == 1 and identities_known and len(identities) > 1:
        answer = (f"No, Moodle muestra más de una persona docente con el nombre {names[0]}. "
                  "No puedo distinguir a cuál te refieres solo por el nombre.")
    elif len(matched) == 1 and identities_known and len(identities) == 1:
        answer = (f"Sí, {matched[0]} es la única docente visible "
                  "en los cursos consultados de Moodle.")
    elif len(matched) == 1 and len(names) > 1:
        others = [name for name in names if name != matched[0]]
        answer = (f"No, además de {matched[0]}, Moodle muestra a " + ", ".join(others) + ".")
    else:
        answer = ("No puedo confirmar esa afirmación. Según Moodle, los docentes visibles son: "
                  + ", ".join(names) + ".")
    if gaps:
        answer += (" No puedo asegurar que no haya otros docentes asignados: no tengo nombres "
                   "visibles en " + ", ".join(gaps) + ".")
    return answer


def calendar_discrepancies(context: dict, sources: list) -> list[str]:
    """Compare unambiguous dates for the same event; leave ambiguous documents unclassified."""
    import re
    from datetime import date
    import unicodedata

    months = {
        name: number
        for number, name in enumerate(
            (
                "enero",
                "febrero",
                "marzo",
                "abril",
                "mayo",
                "junio",
                "julio",
                "agosto",
                "septiembre",
                "octubre",
                "noviembre",
                "diciembre",
            ),
            1,
        )
    }
    notices = []
    for source in sources:
        if source.scope != "institutional" or source.document_type != "CALENDARIO":
            continue
        text = source.excerpt.lower()
        dates = set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text))
        for day, month, year in re.findall(r"\b(\d{1,2}) de (\w+) de (\d{4})\b", text):
            if month not in months:
                continue
            try:
                dates.add(date(int(year), months[month], int(day)).isoformat())
            except ValueError:
                continue
        if len(dates) != 1:
            continue
        official = next(iter(dates))
        for event in context.get("calendar", []):

            def words(value):
                ascii_text = (
                    unicodedata.normalize("NFKD", value.lower()).encode("ascii", "ignore").decode()
                )
                ascii_text = re.sub(r"\binici(?:o|a)|\bempieza|\bcomienza", "inicio", ascii_text)
                return set(re.findall(r"\b[a-z0-9]+\b", ascii_text)) - {
                    "el",
                    "la",
                    "los",
                    "las",
                    "de",
                    "del",
                    "en",
                    "un",
                    "una",
                    "demo",
                    "se",
                    "al",
                }

            eventwords = words(event["name"])
            if len(eventwords) < 2 or not eventwords.issubset(words(source.excerpt)):
                continue
            native = event["starts_date"][:10]
            if native != official:
                notices.append(
                    f"Discrepancia para {event['name']}: Moodle indica {native}; "
                    f"el calendario institucional indica {official} [{source.source_id}]. "
                    "El calendario oficial tiene prioridad."
                )
    return list(dict.fromkeys(notices))
