"""Verify native Moodle navigation using the deployed conversational provider."""
import json
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

root = Path(__file__).resolve().parents[2]
base = 'http://127.0.0.1:8088'
chat = base + '/local/acadassistant/index.php'
values = dict(line.split('=', 1) for line in (root / '.moodle.env').read_text().splitlines() if '=' in line)
report = {'complete': False, 'cases': []}
output = root / '.local/navigation-browser.json'


def login(browser, username):
    context = browser.new_context()
    page = context.new_page()
    page.set_default_navigation_timeout(180000)
    page.goto(base + '/login/index.php')
    page.wait_for_load_state('networkidle')
    page.locator('#username').fill(username)
    page.locator('#password').fill(values['MOODLE_DEMO_PASSWORD'])
    with page.expect_navigation():
        page.locator('#loginbtn').click()
    page.goto(chat)
    return context, page


def ask(page, question):
    start = time.monotonic()
    page.locator('.local-acadassistant-chat--enhanced').wait_for()
    page.locator('#assistant-question').fill(question)
    page.get_by_role('button', name='Send question', exact=True).click()
    page.wait_for_function(
        "document.querySelector('#assistant-form').dataset.submitting === 'false'",
        timeout=180000,
    )
    assert page.locator('.alert-danger').count() == 0, 'Moodle reported an assistant error'
    turn = page.locator('.local-acadassistant-turn').last
    links = turn.locator('a.local-acadassistant-destination')
    result = {'question': question, 'seconds': round(time.monotonic() - start, 3),
              'answer': turn.locator('.local-acadassistant-answer').inner_text(),
              'links': [{'label': a.inner_text(), 'url': a.get_attribute('href')}
                        for a in links.all()]}
    report['cases'].append(result)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(question, result, flush=True)
    return result


with sync_playwright() as p:
    browser = p.chromium.launch()
    try:
        context, page = login(browser, 'estudiante1')
        result = ask(page, 'Mándame a la tarea con la entrega más próxima de llegar a su fecha límite')
        assert len(result['links']) == 2, result
        assert any('Reseña crítica' in link['label'] for link in result['links'])
        assert any('Análisis descriptivo' in link['label'] for link in result['links'])
        for link in result['links']:
            page.goto(link['url'])
            assert '/mod/assign/view.php?id=' in page.url
            assert page.locator('#intro').count() == 1
        page.goto(chat)
        denied = ask(page, 'Abre el curso Metodología de Investigación 103')
        assert denied['links'] == []
        grades = ask(page, 'Abre mis calificaciones de Programacion 104')
        assert len(grades['links']) == 1, grades
        page.goto(grades['links'][0]['url'])
        assert '/grade/report/user/index.php' in page.url
        assert page.locator('.alert-danger,.errorbox').count() == 0
        assert '92' in page.locator('body').inner_text()
        page.goto(chat)
        calendar = ask(page, 'Llévame a mi calendario de Moodle')
        assert len(calendar['links']) == 1, calendar
        page.goto(calendar['links'][0]['url'])
        assert '/calendar/view.php' in page.url
        assert page.locator('.alert-danger,.errorbox').count() == 0
        context.close()
        context, page = login(browser, 'docente2')
        grading = ask(page, 'Llévame a calificar las entregas de Programacion 104, un curso que enseño')
        assert len(grading['links']) == 2, grading
        for link in grading['links']:
            assert 'action=grading' in link['url']
            page.goto(link['url'])
            assert page.locator('.gradingtable').count() >= 1
            if 'Práctica de algoritmos' in link['label']:
                expect(page.locator('.gradingtable')).to_contain_text('92.00')
        page.goto(chat)
        grades = ask(page, 'Abre el libro de calificaciones de Programacion 104, un curso que enseño')
        assert len(grades['links']) == 1, grades
        page.goto(grades['links'][0]['url'])
        assert '/grade/report/grader/index.php' in page.url
        expect(page.locator('body')).to_contain_text('Ana Torres', timeout=30000)
        assert page.locator('.alert-danger,.errorbox').count() == 0
        context.close()
        context, page = login(browser, 'autoridad1')
        courses = ask(page, 'Abre el curso Programacion 104 entre los cursos disponibles que puedo consultar')
        assert len(courses['links']) == 1, courses
        page.goto(courses['links'][0]['url'])
        assert '/course/view.php?id=' in page.url
        context.close()
        report['complete'] = True
    finally:
        browser.close()
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
