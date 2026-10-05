<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

namespace local_acadassistant;

defined('MOODLE_INTERNAL') || die();

/** Tests the academic data returned for the authenticated Moodle user. */
final class academic_context_provider_test extends \advanced_testcase {
    public function test_student_context_contains_own_submission_but_not_another_students(): void {
        global $DB;

        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['fullname' => 'Biología 101']);
        $student = $this->getDataGenerator()->create_user();
        $otherstudent = $this->getDataGenerator()->create_user();
        $this->getDataGenerator()->enrol_user($student->id, $course->id, 'student');
        $this->getDataGenerator()->enrol_user($otherstudent->id, $course->id, 'student');

        $assigngenerator = $this->getDataGenerator()->get_plugin_generator('mod_assign');
        $assignment = $assigngenerator->create_instance([
            'course' => $course->id,
            'name' => 'Informe de laboratorio',
            'duedate' => time() + DAYSECS,
            'assignsubmission_onlinetext_enabled' => 1,
        ]);
        $cm = get_coursemodule_from_instance('assign', $assignment->id, $course->id);
        $assigngenerator->create_submission([
            'userid' => $student->id,
            'cmid' => $cm->id,
            'status' => 'submitted',
            'onlinetext' => 'Mi entrega',
        ]);
        $assigngenerator->create_submission([
            'userid' => $otherstudent->id,
            'cmid' => $cm->id,
            'status' => 'draft',
            'onlinetext' => 'Entrega de otra persona',
        ]);

        $this->setUser($student);
        $assign = new \assign(\context_module::instance($cm->id), $cm, $course);
        $this->assertTrue($assign->submit_for_grading(new \stdClass(), []));
        $before = $DB->get_records('assign_submission', ['assignment' => $assignment->id]);
        $context = (new \local_acadassistant\local\academic_context_provider())
            ->collect_for_question('¿Qué entregas tengo en total, todas, en Biología 101?');
        $after = $DB->get_records('assign_submission', ['assignment' => $assignment->id]);

        $this->assertEquals($before, $after, 'Collecting academic context must be read-only.');
        $this->assertSame([(int)$course->id], $context['course_ids']);
        $this->assertCount(1, $context['academic_context']['assignments']);
        $this->assertSame('submitted', $context['academic_context']['assignments'][0]['status']);
        $this->assertSame((int)$assignment->duedate, $context['academic_context']['assignments'][0]['due_at']);
        $this->assertArrayNotHasKey('userid', $context['academic_context']['assignments'][0]);
    }

    public function test_calendar_query_includes_own_visible_events_not_other_users_events(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['fullname' => 'Ciclo actual']);
        $student = $this->getDataGenerator()->create_user();
        $other = $this->getDataGenerator()->create_user();
        $this->getDataGenerator()->enrol_user($student->id, $course->id, 'student');

        \calendar_event::create([
            'name' => 'Inicio de clases',
            'courseid' => $course->id,
            'groupid' => 0,
            'userid' => $student->id,
            'eventtype' => 'course',
            'timestart' => time() + DAYSECS,
            'timeduration' => 0,
            'visible' => 1,
        ], false);
        \calendar_event::create([
            'name' => 'Evento privado ajeno',
            'courseid' => 0,
            'groupid' => 0,
            'userid' => $other->id,
            'eventtype' => 'user',
            'timestart' => time() + DAYSECS,
            'timeduration' => 0,
            'visible' => 1,
        ], false);

        $this->setUser($student);
        $context = (new \local_acadassistant\local\academic_context_provider())
            ->collect_for_question('¿Cuándo es el evento del calendario?');

        $this->assertSame('Calendario Moodle', $context['academic_context']['calendar'][0]['source']);
        $this->assertSame(['calendar'], $context['requested_categories']);
        $eventnames = array_column($context['academic_context']['calendar'], 'name');
        $this->assertContains('Inicio de clases', $eventnames);
        $this->assertNotContains('Evento privado ajeno', $eventnames);
    }

    public function test_unknown_explicit_course_does_not_fall_back_to_other_courses(): void {
        $this->resetAfterTest();
        $biology = $this->getDataGenerator()->create_course(['fullname' => 'Biología 101']);
        $student = $this->getDataGenerator()->create_user();
        $this->getDataGenerator()->enrol_user($student->id, $biology->id, 'student');
        $this->setUser($student);

        $context = (new \local_acadassistant\local\academic_context_provider())
            ->collect_for_question('¿Qué tareas tengo en Física 201?');

        $this->assertSame([], $context['course_ids']);
        $this->assertArrayNotHasKey('assignments', $context['academic_context']);
        $this->assertNotEmpty($context['academic_context']['query']['notices']);
    }

    /** Permission and course-selection coverage for teacher queries. */
    public function test_teacher_only_receives_named_student_grade_in_authorized_course(): void {
        $this->resetAfterTest();
        $biology = $this->getDataGenerator()->create_course(['fullname' => 'Biología 101']);
        $history = $this->getDataGenerator()->create_course(['fullname' => 'Historia 202']);
        $teacher = $this->getDataGenerator()->create_user();
        $student = $this->getDataGenerator()->create_user([
            'firstname' => 'María',
            'lastname' => 'Estudiante',
        ]);
        $this->getDataGenerator()->enrol_user($teacher->id, $biology->id, 'editingteacher');
        $this->getDataGenerator()->enrol_user($teacher->id, $history->id, 'student');
        $this->getDataGenerator()->enrol_user($student->id, $biology->id, 'student');
        $this->getDataGenerator()->enrol_user($student->id, $history->id, 'student');

        $assigngenerator = $this->getDataGenerator()->get_plugin_generator('mod_assign');
        $biologyassignment = $assigngenerator->create_instance([
            'course' => $biology->id,
            'name' => 'Ensayo',
            'grade' => 100,
        ]);
        $historyassignment = $assigngenerator->create_instance([
            'course' => $history->id,
            'name' => 'Ensayo',
            'grade' => 100,
        ]);
        foreach (
            [[$biology, $biologyassignment, 85], [$history, $historyassignment, 99]]
            as [$course, $assignment, $grade]
        ) {
            $cm = get_coursemodule_from_instance('assign', $assignment->id, $course->id);
            $assigngenerator->create_submission([
                'userid' => $student->id,
                'cmid' => $cm->id,
                'status' => 'submitted',
                'onlinetext' => 'Entrega de prueba',
            ]);
            $gradeitem = \grade_item::fetch([
                'itemtype' => 'mod',
                'itemmodule' => 'assign',
                'iteminstance' => $assignment->id,
                'courseid' => $course->id,
                'itemnumber' => 0,
            ]);
            $gradeitem->update_final_grade($student->id, $grade, 'gradebook');
        }

        $this->setUser($teacher);
        $provider = new \local_acadassistant\local\academic_context_provider();
        $authorized = $provider->collect_for_question(
            '¿Qué calificación tiene María Estudiante en Ensayo de Biología 101?'
        );
        $denied = $provider->collect_for_question(
            '¿Qué calificación tiene María Estudiante en Ensayo de Historia 202?'
        );

        $this->assertSame([(int)$biology->id], $authorized['course_ids']);
        $this->assertCount(1, $authorized['academic_context']['grades']);
        $this->assertSame(
            'María Estudiante',
            $authorized['academic_context']['grades'][0]['participant']
        );
        $this->assertStringContainsString('85', $authorized['academic_context']['grades'][0]['grade']);
        $this->assertSame([(int)$history->id], $denied['course_ids']);
        $this->assertSame([], $denied['academic_context']['grades']);
    }

    public function test_global_capabilities_allow_only_records_available_in_moodle(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['fullname' => 'Administración 301']);
        $student = $this->getDataGenerator()->create_user([
            'firstname' => 'Luis',
            'lastname' => 'Alumno',
        ]);
        $this->getDataGenerator()->enrol_user($student->id, $course->id, 'student');
        $assigngenerator = $this->getDataGenerator()->get_plugin_generator('mod_assign');
        $assignment = $assigngenerator->create_instance([
            'course' => $course->id,
            'name' => 'Trabajo final',
            'grade' => 100,
        ]);
        $cm = get_coursemodule_from_instance('assign', $assignment->id, $course->id);
        $assigngenerator->create_submission([
            'userid' => $student->id,
            'cmid' => $cm->id,
            'status' => 'submitted',
        ]);
        $gradeitem = \grade_item::fetch([
            'itemtype' => 'mod',
            'itemmodule' => 'assign',
            'iteminstance' => $assignment->id,
            'courseid' => $course->id,
            'itemnumber' => 0,
        ]);
        $gradeitem->update_final_grade($student->id, 90, 'gradebook');

        $this->setAdminUser();
        $context = (new \local_acadassistant\local\academic_context_provider())
            ->collect_for_question(
                '¿Qué calificación tiene Luis Alumno en Trabajo final de Administración 301?'
            );

        $this->assertSame([(int)$course->id], $context['course_ids']);
        $this->assertCount(1, $context['academic_context']['grades']);
        $this->assertSame('Luis Alumno', $context['academic_context']['grades'][0]['participant']);
        $this->assertStringContainsString('90', $context['academic_context']['grades'][0]['grade']);
    }
    public function test_equivalent_course_questions_do_not_inherit_unrelated_tasks(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['fullname' => 'Álgebra 101']);
        $student = $this->getDataGenerator()->create_user();
        $this->getDataGenerator()->enrol_user($student->id, $course->id, 'student');
        $this->setUser($student);
        $provider = new \local_acadassistant\local\academic_context_provider();
        foreach (['¿Qué materias llevo?', '¿En qué estoy matriculado?', '¿Qué cursos tengo?'] as $question) {
            $result = $provider->collect_for_question($question, [[
                'question' => '¿Qué tareas tengo?', 'answer' => 'Dos tareas.',
            ]]);
            $this->assertSame(['courses'], $result['requested_categories']);
            $this->assertSame('Álgebra 101', $result['academic_context']['courses'][0]['name']);
        }
    }
    public function test_membership_and_teaching_are_not_global_access(): void {
        $this->resetAfterTest();
        $generator = $this->getDataGenerator();
        $own = $generator->create_course(['fullname' => 'Curso propio']);
        $other = $generator->create_course(['fullname' => 'Curso ajeno']);
        $user = $generator->create_user();
        $generator->enrol_user($user->id, $own->id, 'editingteacher');
        role_assign((int)$GLOBALS['DB']->get_field('role', 'id', ['shortname' => 'manager'], MUST_EXIST), $user->id, \context_system::instance()->id);
        $this->setUser($user);
        $provider = new \local_acadassistant\local\academic_context_provider();
        foreach (['¿Qué cursos tengo?', '¿Qué cursos enseño?'] as $question) {
            $result = $provider->collect_for_question($question);
            $this->assertSame(['Curso propio'], array_column($result['academic_context']['courses'], 'name'));
            $this->assertContains((int)$other->id, $result['course_ids']);
        }
        $result = $provider->collect_for_question('¿Qué cursos puedo consultar?');
        $this->assertCount(2, $result['academic_context']['courses']);
    }
    public function test_teachers_respect_participants_and_separate_groups(): void {
        $this->resetAfterTest();
        $generator = $this->getDataGenerator();
        $course = $generator->create_course(['fullname' => 'Biología', 'groupmode' => SEPARATEGROUPS]);
        $student = $generator->create_user();
        $visible = $generator->create_user(['firstname' => 'Carla', 'lastname' => 'Visible']);
        $hidden = $generator->create_user(['firstname' => 'Ana', 'lastname' => 'Otrogrupo']);
        $generator->enrol_user($student->id, $course->id, 'student');
        foreach ([$visible, $hidden] as $teacher) {
            $generator->enrol_user($teacher->id, $course->id, 'editingteacher');
        }
        $group = $generator->create_group(['courseid' => $course->id]);
        groups_add_member($group, $student);
        groups_add_member($group, $visible);
        $this->setUser($student);
        $provider = new \local_acadassistant\local\academic_context_provider();
        $result = $provider->collect_for_question('¿Cómo se llaman mis profesores?');
        $this->assertSame(['Carla Visible'], $result['academic_context']['teachers'][0]['names']);
        assign_capability('moodle/course:viewparticipants', CAP_PROHIBIT,
            (int)$GLOBALS['DB']->get_field('role', 'id', ['shortname' => 'student']),
            \context_course::instance($course->id)->id);
        accesslib_clear_all_caches_for_unit_testing();
        $result = $provider->collect_for_question('¿Quiénes son mis docentes?');
        $this->assertSame([], $result['academic_context']['teachers'][0]['names']);
        $this->assertSame('unavailable', $result['academic_context']['teachers'][0]['state']);
    }
    public function test_course_pages_are_complete_and_recheck_membership(): void {
        $this->resetAfterTest();
        $generator = $this->getDataGenerator();
        $student = $generator->create_user();
        $courses = [];
        for ($i = 0; $i < 22; $i++) {
            $course = $generator->create_course(['fullname' => sprintf('Curso %02d', $i)]);
            $generator->enrol_user($student->id, $course->id, 'student');
            $courses[] = $course;
        }
        $this->setUser($student);
        $provider = new \local_acadassistant\local\academic_context_provider();
        $first = $provider->collect_for_question('¿Qué cursos tengo?');
        $this->assertTrue($first['academic_context']['query']['has_more']);
        $second = $provider->collect_for_question('¿Qué cursos tengo?', [], 20);
        $this->assertFalse($second['academic_context']['query']['has_more']);
        $this->assertSame(['Curso 20', 'Curso 21'], array_column($second['academic_context']['courses'], 'name'));
        $instances = enrol_get_instances($courses[20]->id, true);
        $instance = reset($instances);
        enrol_get_plugin($instance->enrol)->unenrol_user($instance, $student->id);
        accesslib_clear_all_caches_for_unit_testing();
        $fresh = $provider->collect_for_question('¿Qué cursos tengo?', [], 0, $first['continuation_seen']);
        $this->assertSame(['Curso 21'], array_column($fresh['academic_context']['courses'], 'name'));
        $this->assertNotContains((int)$courses[20]->id, $fresh['course_ids']);

    }
    public function test_institution_in_mixed_question_is_not_an_unknown_course(): void {
        $this->resetAfterTest();
        $generator = $this->getDataGenerator();
        $course = $generator->create_course(['fullname' => 'Algebra 101']);
        $student = $generator->create_user();
        $generator->enrol_user($student->id, $course->id, 'student');
        $this->setUser($student);
        $result = (new \local_acadassistant\local\academic_context_provider())->collect_for_question(
            '¿Qué cursos tengo y cuál es la nota mínima aprobatoria en Universidad Demo del Valle?');
        $this->assertSame('Algebra 101', $result['academic_context']['courses'][0]['name']);
        $this->assertSame([(int)$course->id], $result['course_ids']);
    }
    public function test_delivered_question_returns_presented_work_not_pending(): void {
        $this->resetAfterTest();
        $generator = $this->getDataGenerator();
        $course = $generator->create_course();
        $student = $generator->create_user();
        $generator->enrol_user($student->id, $course->id, 'student');
        $assignmentgenerator = $generator->get_plugin_generator('mod_assign');
        $assignment = $assignmentgenerator->create_instance([
            'course' => $course->id, 'name' => 'Trabajo entregado', 'assignsubmission_onlinetext_enabled' => 1,
        ]);
        $cm = get_coursemodule_from_instance('assign', $assignment->id, $course->id);
        $assignmentgenerator->create_submission(['userid' => $student->id, 'cmid' => $cm->id,
            'onlinetext' => 'Entrega de prueba']);
        $this->setUser($student);
        $assign = new \assign(\context_module::instance($cm->id), $cm, $course);
        $assign->submit_for_grading(new \stdClass(), []);
        $result = (new \local_acadassistant\local\academic_context_provider())
            ->collect_for_question('¿Qué he entregado?');
        $this->assertSame('submitted', $result['academic_context']['query']['assignment_filter']);
        $this->assertSame('Trabajo entregado', $result['academic_context']['assignments'][0]['name']);
    }
    public function test_teacher_synonyms_and_repeated_followups_keep_the_operation(): void {
        $this->resetAfterTest();
        $generator = $this->getDataGenerator();
        $course = $generator->create_course(['fullname' => 'Biologia 102']);
        $student = $generator->create_user();
        $teacher = $generator->create_user(['firstname' => 'Carla', 'lastname' => 'Docente']);
        $generator->enrol_user($student->id, $course->id, 'student');
        $generator->enrol_user($teacher->id, $course->id, 'editingteacher');
        $this->setUser($student);
        $provider = new \local_acadassistant\local\academic_context_provider();
        $result = $provider->collect_for_question('¿Quiénes me enseñan?');
        $this->assertSame(['teachers'], $result['requested_categories']);
        $this->assertSame(['Carla Docente'], $result['academic_context']['teachers'][0]['names']);
        $history = [['question' => '¿Quiénes son mis profesores?', 'answer' => 'Carla.'],
            ['question' => '¿Y en Biologia 102?', 'answer' => 'Carla.']];
        $result = $provider->collect_for_question('¿Y en Biologia 102?', $history);
        $this->assertSame(['teachers'], $result['requested_categories']);
        $this->assertSame(['Carla Docente'], $result['academic_context']['teachers'][0]['names']);
    }
    public function test_document_code_does_not_request_unrelated_assignments(): void {
        $this->resetAfterTest();
        $generator = $this->getDataGenerator();
        $course = $generator->create_course(['fullname' => 'Reservado 103']);
        $student = $generator->create_user();
        $generator->enrol_user($student->id, $course->id, 'student');
        $this->setUser($student);
        $result = (new \local_acadassistant\local\academic_context_provider())->collect_for_question(
            '¿Cuál es el código de entrega del proyecto del curso Reservado 103?');
        $this->assertSame([], $result['requested_categories']);
        $this->assertSame([(int)$course->id], $result['course_ids']);
        $this->assertArrayNotHasKey('assignments', $result['academic_context']);
    }
    public function test_mixed_courses_preserve_independent_document_authorization(): void {
        $this->resetAfterTest();
        $generator = $this->getDataGenerator();
        $biology = $generator->create_course(['fullname' => 'Biologia 102']);
        $algebra = $generator->create_course(['fullname' => 'Algebra 101']);
        $student = $generator->create_user();
        foreach ([$biology, $algebra] as $course) {
            $generator->enrol_user($student->id, $course->id, 'student');
            $generator->get_plugin_generator('mod_assign')->create_instance([
                'course' => $course->id, 'name' => 'Tarea del curso',
            ]);
        }
        $this->setUser($student);
        $result = (new \local_acadassistant\local\academic_context_provider())->collect_for_question(
            '¿Qué tareas tengo en Biologia 102 y cuál es el código de tutoría de Algebra 101?');
        $this->assertSame([(int)$algebra->id], $result['academic_context']['query']['document_course_ids']);
        $this->assertContains((int)$algebra->id, $result['course_ids']);
        $this->assertSame([(int)$biology->id], array_column($result['academic_context']['assignments'], 'course_id'));
    }
}
