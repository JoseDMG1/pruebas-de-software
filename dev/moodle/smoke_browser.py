"""Exercise the real localhost Moodle chat with fictional accounts and Ollama."""
import json
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[2]
base = "http://127.0.0.1:8088"
chaturl = base + "/local/acadassistant/index.php"
values = dict(line.split("=", 1) for line in (root / ".moodle.env").read_text().splitlines() if "=" in line)
password = values["MOODLE_DEMO_PASSWORD"]
report = {}


def login(page, username):
    page.goto(base + "/login/index.php")
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    with page.expect_navigation():
        page.locator("#loginbtn").click()
    page.goto(chaturl)
    assert page.locator("#assistant-question").count() == 1
    assert page.locator("nav a[href*='/local/acadassistant/index.php']").count() >= 1


def ask(page, question):
    page.locator("#assistant-question").fill(question)
    with page.expect_navigation(timeout=180000):
        page.get_by_role("button", name="Send question", exact=True).click(timeout=180000)
    assert page.locator(".alert-danger").count() == 0, page.locator("body").inner_text()
    turns = page.locator(".local-acadassistant-turn")
    assert turns.count() > 0
    answer = turns.last.locator("p").nth(1).inner_text()
    assert values["MOODLE_RAG_SHARED_SECRET"] not in page.content()
    assert "Bearer " not in page.content()
    print("Verified query:", question, flush=True)
    return answer


def clear(page):
    with page.expect_navigation():
        page.get_by_role("button", name="New conversation", exact=True).click()
    assert page.locator(".local-acadassistant-turn").count() == 0


with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    context = browser.new_context(viewport={"width": 1280, "height": 960})
    page = context.new_page()
    page.set_default_navigation_timeout(180000)
    page.goto(chaturl)
    assert page.locator("#assistant-question").count() == 0
    report["anonymous_denied"] = True
    login(page, "estudiante1")
    answer = ask(page, "¿Qué tareas tengo pendientes?")
    report["student_pending"] = answer
    assert "ecuaciones" in answer.lower() and "laboratorio" in answer.lower(), answer
    report["follow_up"] = ask(page, "¿Y cuándo vencen?")
    assert page.locator(".local-acadassistant-turn").count() == 2
    page.screenshot(path=str(root / ".local/moodle-student.png"), full_page=True)
    clear(page)
    report["financial_limit"] = ask(page, "cuánto me está costando las cuotas?")
    assert "todavía no consulta" in report["financial_limit"]
    report["teacher_names"] = ask(page, "cuáles son todos los nombres de mis profesores?")
    assert "Carla Docente" in report["teacher_names"]
    assert "Carla Docente" in ask(page, "¿Quiénes me enseñan?")
    assert "Carla Docente" in ask(page, "¿Y en Biologia 102?")
    assert "Algebra 101" in ask(page, "¿Y en Algebra 101?")
    assert "Carla Docente" in ask(page, "¿Y en Biologia 102?")
    for question in ["qué cursos tengo?", "qué cursos tengo?", "¿Qué materias llevo?", "¿En qué estoy matriculado?"]:
        answer = ask(page, question)
        assert "Algebra 101" in answer and "Biologia 102" in answer, answer
        assert page.locator(".local-acadassistant-turn").last.locator("details").count() == 0
    report["reported_sequence_and_variants"] = True
    report["mixed_financial"] = ask(page, "¿Qué cursos tengo y cuánto debo pagar?")
    assert "Algebra 101" in report["mixed_financial"] and "pagos personales" in report["mixed_financial"]
    ask(page, "¿Qué tareas tengo?")
    report["ambiguous_followup"] = ask(page, "¿Cuándo vence esa tarea?")
    assert "¿De cuál tarea" in report["ambiguous_followup"]
    report["resolved_followup"] = ask(page, "Ejercicios de ecuaciones")
    assert "Ejercicios de ecuaciones" in report["resolved_followup"]
    assert "Informe de laboratorio" not in report["resolved_followup"]
    ask(page, "¿Qué tareas tengo?")
    ask(page, "¿Cuándo vence esa tarea?")
    newtopic = ask(page, "¿Qué cursos tengo?")
    assert "Algebra 101" in newtopic and "Biologia 102" in newtopic
    clear(page)
    report["mixed_documentary"] = ask(page,
        "¿Qué cursos tengo y cuál es la nota mínima aprobatoria en Universidad Demo del Valle?")
    assert "Algebra 101" in report["mixed_documentary"] and "11" in report["mixed_documentary"], report["mixed_documentary"]
    report["independent_mixed_course_scopes"] = ask(page,
        "¿Qué tareas tengo en Biologia 102 y cuál es el código de tutoría de Algebra 101?")
    assert "Informe de laboratorio" in report["independent_mixed_course_scopes"]
    assert "ALG-TUTOR-16" in report["independent_mixed_course_scopes"], report["independent_mixed_course_scopes"]
    assert "Documento de prueba ALG101" in page.locator(".local-acadassistant-turn").last.inner_text()
    clear(page)
    report["new_conversation_cleared"] = True
    report["institutional"] = ask(page, "¿Cuál es la nota mínima aprobatoria en Universidad Demo del Valle?")
    assert "11" in report["institutional"], report["institutional"]
    assert page.locator(".local-acadassistant-turn details").count() > 0
    clear(page)
    report["restricted_denied"] = ask(page, "¿Cuál es el código de entrega del proyecto del curso Reservado 103?")
    assert page.locator(".local-acadassistant-turn").last.locator("details").count() == 0
    assert "ORQUIDEA-73" not in page.locator(".local-acadassistant-turn").inner_text()
    # Backdate only this fixture account's session, then exercise Moodle's native timeout.
    subprocess.run(["docker", "compose", "-f", "compose.moodle.yaml", "exec", "-T", "-u", "www-data",
                    "moodle", "php", "/opt/moodle-dev/expire-session.php", "estudiante1"], cwd=root, check=True)
    page.goto(chaturl)
    assert page.locator("#assistant-question").count() == 0
    login(page, "estudiante1")
    assert page.locator(".local-acadassistant-turn").count() == 0
    report["actual_session_timeout_cleared"] = True
    ask(page, "¿A qué hora es la tutoría del curso Algebra 101?")
    logout = page.locator("a[href*='/login/logout.php']").first.get_attribute("href")
    page.goto(logout)
    login(page, "estudiante1")
    assert page.locator(".local-acadassistant-turn").count() == 0
    report["logout_cleared"] = True
    context.close()
    for username, question, expected in [
        ("estudiante2", "¿Cuál es el código de entrega del proyecto del curso Reservado 103?", "ORQUIDEA-73"),
        ("docente1", "¿Qué calificación tiene Luis Prueba en Biologia 102?", "85"),
        ("autoridad1", "¿Qué cursos están disponibles?", "Reservado"),
    ]:
        context = browser.new_context()
        page = context.new_page()
        page.set_default_navigation_timeout(180000)
        login(page, username)
        if username == "estudiante2":
            empty = ask(page, "¿Qué tareas tengo pendientes en Biologia 102?")
            assert "no tienes tareas pendientes" in empty, empty
            submitted = ask(page, "¿Qué he entregado en Biologia 102?")
            assert "Informe de laboratorio" in submitted and "entregada" in submitted
        if username == "autoridad1":
            own = ask(page, "¿Qué cursos tengo?")
            assert "no hay cursos" in own and "Reservado 103" not in own
        report[username] = ask(page, question)
        assert expected.lower() in report[username].lower(), report[username]
        if username == "estudiante2":
            assert page.locator(".local-acadassistant-turn").last.locator("details").count() > 0
            assert "Documento de prueba RES103" in page.locator(".local-acadassistant-turn").last.inner_text()
        context.close()
        print("Verified", username, flush=True)
    subprocess.run(["docker", "compose", "-f", "compose.moodle.yaml", "exec", "-T", "-u", "www-data",
                    "moodle", "php", "/opt/moodle-dev/pagination-fixtures.php"], cwd=root, check=True)
    context = browser.new_context()
    page = context.new_page()
    login(page, "estudiante_lista")
    first = ask(page, "¿Qué materias llevo?")
    assert "Z Lista 01" in first and "Z Lista 20" in first and "parcial" in first
    second = ask(page, "continúa")
    assert "Z Lista 21" in second and "Z Lista 22" in second and "Z Lista 01" not in second
    assert "parcial" not in second
    clear(page)
    assert "No hay una lista pendiente" in ask(page, "continúa")
    report["pagination_and_cursor_reset"] = True
    context.close()
    browser.close()

(root / ".local/moodle-browser-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
print(json.dumps(report, indent=2, ensure_ascii=False))
