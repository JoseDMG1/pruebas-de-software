from capacity_http import Page


def test_parser_uses_last_turn_and_excludes_navigation_from_answer():
    html = '''<html><body><input name="sesskey" value="not-exported"><a href="/calendar/view.php">Navigation</a>
    <article class="local-acadassistant-turn"><div class="local-acadassistant-answer">Old</div></article>
    <article class="local-acadassistant-turn"><div class="local-acadassistant-answer"><p>Nota <b>11</b><br>actual</p></div><span>Reglamento [1]</span><a href="/calendar/view.php">Destino</a></article>
    <script>document</script></body></html>'''
    page = Page(html)
    assert ' '.join(page.answer) == 'Nota  11 actual'
    assert 'Old' not in page.turn and 'document' not in page.turn
    assert len(page.links) == 1
    assert page.inputs['sesskey'] == 'not-exported'


def test_parser_detects_application_error():
    assert Page('<div class="alert alert-danger">Error</div>').error
