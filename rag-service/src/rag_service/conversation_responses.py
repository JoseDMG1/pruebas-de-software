"""Bounded responses: facts come from authorized reads, never from model examples."""

from rag_service.academic_answers import AcademicPlan, compose_academic, calendar_discrepancies
from rag_service.errors import AppError
import psycopg


CAPABILITIES = (
    "Puedo ayudarte con información institucional, el uso de Moodle, tus cursos, "
    "docentes, tareas y calificaciones visibles, y organizar tu estudio."
)
SOCIAL = {
    "greeting": "¡Hola! Estoy listo para ayudarte con tu vida universitaria. ¿Qué necesitas?",
    "thanks": "¡De nada! Si necesitas más ayuda con tu vida universitaria, aquí estoy.",
    "bye": "¡Hasta luego! Que te vaya bien con tus estudios.",
}


def respond(service, question, proposal, runtime, context, history, course_ids, request_id):
    from rag_service.query import QueryResponse

    sources = []
    insufficient = False
    if proposal.intent == "social":
        answer = SOCIAL[proposal.social]
    elif proposal.intent == "capabilities":
        answer = CAPABILITIES
    elif proposal.intent == "blocked":
        answer = "Mi ayuda se limita a la vida universitaria. " + CAPABILITIES
    elif proposal.intent == "clarify":
        answer = {
            "intent": "¿Qué información o ayuda universitaria necesitas?",
            "course": "¿De qué curso necesitas esa información?",
            "task": "¿A qué tarea y curso te refieres?",
            "week": "¿Qué semana quieres organizar? Indica las fechas.",
            "availability": "¿Qué días y horas tienes disponibles para estudiar?",
        }[proposal.clarification]
    else:
        try:
            plan = AcademicPlan.model_validate(context["query"])
            if plan.categories != proposal.categories:
                raise ValueError("Los resultados no corresponden a las operaciones propuestas.")
            if proposal.intent == "weekly_plan":
                from rag_service.weekly_plan import compose_week

                answer = compose_week(context, plan, proposal, runtime)
            else:
                answer = compose_academic(
                    context,
                    plan,
                    proposal.teacher_reference or question
                    if plan.teacher_confirmation
                    else question,
                )
                if answer.startswith("Según Moodle:\n"):
                    answer = (
                        answer.removeprefix("Según Moodle:\n")
                        + "\nSegún los datos visibles de Moodle."
                    )
            if plan.document_question:
                try:
                    result = service.documentary_evidence(
                        plan.document_question,
                        tuple(plan.document_course_ids or ()),
                        request_id,
                        question,
                    )
                    answer += ("\n" if answer else "") + (
                        result.answer
                        if not result.insufficient_context
                        else "No encontré una fuente verificada para esa consulta. "
                        "No puedo confirmar normas o pasos sin esa evidencia."
                    )
                    sources = result.sources
                    discrepancies = calendar_discrepancies(context, sources)
                    if discrepancies:
                        answer += "\n" + "\n".join(discrepancies)
                    insufficient = not bool(proposal.categories) and result.insufficient_context
                except (AppError, psycopg.Error):
                    if not proposal.categories:
                        raise
                    answer += (
                        "\nNo pude verificar la parte documental; puedes reintentar esa parte."
                    )
        except (KeyError, TypeError, ValueError) as exc:
            raise AppError(
                "invalid_academic_context", "No pude verificar los datos de Moodle."
            ) from exc
    if proposal.finance:
        answer += "\nTodavía no consulto cuotas, saldos ni pagos personales."
    if proposal.blocked_part and proposal.intent != "blocked":
        answer += (
            "\nSolo puedo atender la parte de tu solicitud que corresponde a la vida universitaria."
        )
    if proposal.social != "none" and proposal.intent not in ("social", "blocked"):
        answer = {"greeting": "¡Hola! ", "thanks": "¡De nada! ", "bye": "¡Hasta luego! "}[
            proposal.social
        ] + answer
    if not answer.strip() or len(answer) > 4000:
        raise AppError("invalid_generation", "La respuesta no pudo verificarse. Acota la consulta.")
    return QueryResponse(
        answer=answer, sources=sources, insufficient_context=insufficient, request_id=request_id
    )
