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
        $before = $DB->get_records('assign_submission', ['assignment' => $assignment->id]);
        $context = (new \local_acadassistant\local\academic_context_provider())
            ->collect_for_question('¿Qué entregas tengo pendientes en Biología 101?');
        $after = $DB->get_records('assign_submission', ['assignment' => $assignment->id]);

        $this->assertEquals($before, $after, 'Collecting academic context must be read-only.');
        $this->assertSame([$course->id], $context['course_ids']);
        $this->assertCount(1, $context['academic_context']['assignments']);
        $this->assertSame('submitted', $context['academic_context']['assignments'][0]['status']);
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
        $this->assertSame([], $context['academic_context']['assignments']);
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

        $this->assertSame([$biology->id], $authorized['course_ids']);
        $this->assertCount(1, $authorized['academic_context']['grades']);
        $this->assertSame(
            'María Estudiante',
            $authorized['academic_context']['grades'][0]['participant']
        );
        $this->assertStringContainsString('85', $authorized['academic_context']['grades'][0]['grade']);
        $this->assertSame([$history->id], $denied['course_ids']);
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

        $this->assertSame([$course->id], $context['course_ids']);
        $this->assertCount(1, $context['academic_context']['grades']);
        $this->assertSame('Luis Alumno', $context['academic_context']['grades'][0]['participant']);
        $this->assertStringContainsString('90', $context['academic_context']['grades'][0]['grade']);
    }
}
