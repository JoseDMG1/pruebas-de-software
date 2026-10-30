from capacity_chat import semantic_check, summary


def test_fast_wrong_answer_is_failure():
    assert not semantic_check('rule', 'La nota es 20', 'reglamento [1]', [], {})
    assert semantic_check('rule', 'La nota es 11', 'reglamento [1]', [], {})
    result = summary([{'seconds': 1, 'ok': False, 'error': 'semantic_mismatch'}], 2)
    assert not result['accepted'] and result['semantic_errors'] == 1


def test_courses_require_profile_and_forbid_restricted_course():
    profile = {'expected_courses': ['Álgebra 101', 'Biología 102']}
    assert semantic_check('courses', 'Algebra 101 y Biologia 102', '', [], profile)
    assert not semantic_check('courses', 'Algebra 101', '', [], profile)
    assert not semantic_check('courses', 'Algebra 101 Biologia 102 Metodología de Investigación 103', '', [], profile)


def test_calendar_rejects_foreign_url_and_unknown_checker():
    assert semantic_check('calendar', '', '', ['http://127.0.0.1:8088/calendar/view.php'], {})
    assert not semantic_check('calendar', '', '', ['https://evil.invalid/calendar/view.php'], {})
    assert not semantic_check('unknown', 'respuesta', 'respuesta', [], {})


def test_p99_keeps_timeout():
    samples = [{'seconds': 1, 'ok': True} for _ in range(98)] + [{'seconds': 150, 'ok': False}]*2
    assert summary(samples, 200)['p99_seconds'] == 150
    assert not summary(samples, 200)['accepted']


def test_support_checks_booking_instructions_not_unasked_price():
    answer = 'Las citas se solicitan por correo a bienestar@udv.edu.pe.'
    assert semantic_check('support', answer, answer + ' [1]', [], {})
    assert not semantic_check('support', 'Atención gratuita', '[1]', [], {})


def test_restricted_course_is_relative_to_each_profile():
    profile = {'expected_courses': ['Metodología de Investigación 103'], 'forbidden_courses': ['Algebra 101']}
    assert semantic_check('courses', 'Metodología de Investigación 103', '', [], profile)
    assert not semantic_check('courses', 'Metodología de Investigación 103 Algebra 101', '', [], profile)


def test_extended_workloads_do_not_accept_generic_answers():
    assert not semantic_check('tasks', 'Tienes pendientes', '', [], {})
    assert semantic_check('tasks', 'Tareas pendientes Biología: Informe de laboratorio', '', [], {})
    assert not semantic_check('weekly', 'Plan completo sin pendientes', '', [], {})
    assert semantic_check('weekly', 'Plan: borrador provisional Informe de laboratorio', '', [], {})
