"""Check chat scroll, notification layout, keyboard and error recovery in live Moodle.

POST responses are intercepted in the browser; no AI requests or stored chat writes.
Run from the repository root: rag-service/.venv/bin/python dev/moodle/smoke_chat_ui.py
"""
import json
import time
from pathlib import Path
from html import escape
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[2]
base = 'http://127.0.0.1:8088'
chaturl = base + '/local/acadassistant/index.php'
values = dict(line.split('=', 1) for line in (root / '.moodle.env').read_text().splitlines() if '=' in line)


def check(browser, label, viewport):
    context = browser.new_context(viewport=viewport)
    page = context.new_page()
    page.goto(base + '/login/index.php')
    page.wait_for_load_state('networkidle')
    page.locator('#username').fill('estudiante1')
    page.locator('#password').fill(values['MOODLE_DEMO_PASSWORD'])
    page.locator('#loginbtn').click()
    page.wait_for_url(lambda url: '/login/' not in url)
    page.goto(chaturl)
    page.wait_for_load_state('networkidle')
    page.wait_for_function("document.querySelector('.local-acadassistant-chat--enhanced')")
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.locator('#conversation').evaluate('''node => {
        node.innerHTML = Array.from({length: 18}, (_, i) => `<article class="local-acadassistant-turn"><div class="local-acadassistant-message local-acadassistant-message--user"><div class="local-acadassistant-message__bubble"><p>Pregunta ${i}</p></div></div><div class="local-acadassistant-message local-acadassistant-message--assistant"><div class="local-acadassistant-message__bubble"><div class="local-acadassistant-answer"><p>${'Contenido de ejemplo. '.repeat(35)}</p></div></div></div></article>`).join('');
        node.scrollTop = node.scrollHeight;
    }''')
    page.wait_for_timeout(700)
    routes = []

    def intercept(route):
        if route.request.method == 'POST':
            routes.append(route)
        else:
            route.continue_()
    page.route('**/local/acadassistant/index.php*', intercept)
    navigations = []
    page.on('framenavigated', lambda frame: navigations.append(frame.url) if frame == page.main_frame else None)
    question = 'Pregunta de interfaz controlada'
    page.locator('#assistant-question').fill(question)
    page.locator('#assistant-question').press('Enter')
    page.wait_for_function("document.querySelector('#assistant-form').dataset.submitting === 'true'", timeout=5000)
    deadline = time.monotonic() + 5
    while not routes and time.monotonic() < deadline:
        page.wait_for_timeout(50)
    assert routes, 'No se envió con Enter'
    page.wait_for_timeout(700)
    assert page.locator('#conversation').evaluate('e => e.scrollHeight - e.clientHeight - e.scrollTop') < 3
    page.locator('#conversation').evaluate('e => {e.scrollTop = 600;}')
    page.wait_for_timeout(700)
    position = page.locator('#conversation').evaluate('e => e.scrollTop')
    composer_before = page.locator('#assistant-form').bounding_box()
    response_turn = '<article class="local-acadassistant-turn"><div class="local-acadassistant-message local-acadassistant-message--user"><div class="local-acadassistant-message__bubble"><p>' + escape(question) + '</p></div></div><div class="local-acadassistant-message local-acadassistant-message--assistant"><div class="local-acadassistant-message__bubble"><div class="local-acadassistant-answer"><p>' + 'Respuesta nueva de ejemplo. ' * 55 + '</p></div></div></div></article>'
    # A controlled HTML response exercises the real frontend without calling the AI provider.
    response = '<html><body><div class="local-acadassistant-chat"><div id="conversation">' + response_turn + '</div></div></body></html>'
    routes.pop().fulfill(status=200, content_type='text/html', body=response)
    page.wait_for_timeout(800)
    assert not navigations, 'La respuesta recarga la página y pierde la posición de lectura'
    assert page.locator('#conversation').evaluate('e => e.scrollTop') == position, 'Se movió la lectura al responder'
    assert page.locator('#assistant-latest').is_visible(), 'Falta el aviso de respuesta nueva'
    assert page.locator('#assistant-question').evaluate('e => document.activeElement === e')
    composer_after = page.locator('#assistant-form').bounding_box()
    assert abs(composer_before['y'] - composer_after['y']) < 1, 'El aviso desplaza el formulario'
    box = page.locator('.local-acadassistant-conversation-shell').bounding_box()
    button = page.locator('#assistant-latest').bounding_box()
    assert box['y'] <= button['y'] and button['y'] + button['height'] <= box['y'] + box['height']
    assert abs(button['x'] + button['width'] / 2 - box['x'] - box['width'] / 2) < 2
    assert page.locator('#assistant-latest svg').count() == 1
    gray = page.locator('#assistant-latest').evaluate("e => getComputedStyle(e).color.match(/[0-9.]+/g).slice(0, 3).map(Number)")
    assert max(gray) - min(gray) < 45, gray
    page.screenshot(path=str(root / f'.local/chat-notification-{label}.png'), full_page=True)
    page.locator('#assistant-latest').click()
    page.wait_for_function("(() => { const e = document.querySelector('#conversation'); return e.scrollHeight - e.clientHeight - e.scrollTop < 3; })()")
    assert page.locator('#conversation').evaluate('e => e.scrollHeight - e.clientHeight - e.scrollTop') < 3
    assert page.locator('#assistant-latest').is_hidden()
    page.locator('#assistant-question').fill('Primera línea')
    page.locator('#assistant-question').press('Shift+Enter')
    assert page.locator('#assistant-question').input_value() == 'Primera línea\n'
    assert not routes, 'Shift+Enter envía el mensaje'
    assert page.locator('#assistant-question').evaluate('e => document.activeElement === e')
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')

    # Staying at the bottom follows the next answer, with no reset to the beginning.
    page.locator('#assistant-question').fill(question)
    page.locator('#assistant-question').press('Enter')
    page.wait_for_timeout(200)
    assert len(routes) == 1
    page.locator('#assistant-form').evaluate('e => e.requestSubmit()')
    page.wait_for_timeout(100)
    assert len(routes) == 1, 'Se duplicó el envío mientras estaba pendiente'
    routes.pop().fulfill(status=200, content_type='text/html', body=response)
    page.wait_for_function("document.querySelector('#assistant-form').dataset.submitting === 'false'")
    assert page.locator('#conversation').evaluate('e => e.scrollHeight - e.clientHeight - e.scrollTop') < 3
    assert page.locator('#assistant-latest').is_hidden()

    # An unavailable service restores the question and allows a retry.
    page.locator('#assistant-question').fill(question)
    page.locator('#assistant-question').press('Enter')
    page.wait_for_timeout(200)
    assert len(routes) == 1
    routes.pop().fulfill(status=503, body='Unavailable')
    page.wait_for_function("document.querySelector('#assistant-form').dataset.submitting === 'false'")
    assert page.locator('#assistant-question').input_value() == question
    assert page.locator('#assistant-question').evaluate('e => !e.readOnly')
    assert page.locator('#assistant-send').is_enabled()
    assert page.locator('#assistant-error').is_visible()
    page.locator('#assistant-question').press('Enter')
    page.wait_for_timeout(200)
    assert len(routes) == 1
    routes.pop().fulfill(status=200, content_type='text/html', body=response)
    page.wait_for_function("document.querySelector('#assistant-form').dataset.submitting === 'false'")
    assert page.locator('#assistant-error').count() == 0

    # Exercise the real POST/redirect/GET path with a validation error, without AI calls.
    page.unroute('**/local/acadassistant/index.php*', intercept)
    page.locator('#assistant-question').evaluate('e => {e.maxLength = 2000;}')
    page.locator('#assistant-question').fill('x' * 1001)
    page.locator('#assistant-question').press('Enter')
    page.wait_for_function("document.querySelector('#assistant-form').dataset.submitting === 'false'")
    assert '1000' in page.locator('#assistant-error').inner_text()
    assert page.locator('#assistant-question').input_value() == 'x' * 1001
    assert not navigations
    assert not errors, errors
    context.close()
    return {'viewport': viewport, 'complete': True, 'provider_calls': 0}


if __name__ == '__main__':
    (root / '.local').mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            report = {
                'desktop': check(browser, 'desktop', {'width': 1280, 'height': 1100}),
                'mobile': check(browser, 'mobile', {'width': 390, 'height': 844}),
            }
        finally:
            browser.close()
    (root / '.local/chat-ui-browser.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
