<?php
// This file is part of Moodle - http://moodle.org/
// Licensed under the GNU General Public License version 3 or later.

namespace local_acadassistant;
defined('MOODLE_INTERNAL') || die();

/** Public signed conversation contract tests. */
final class conversation_test extends \advanced_testcase {
    public function test_repeated_selected_task_followups_keep_a_stable_native_reference(): void {
        global $CFG;
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['fullname' => 'Seminario']);
        $student = $this->getDataGenerator()->create_user();
        $this->getDataGenerator()->enrol_user($student->id, $course->id, 'student');
        $assignment = $this->getDataGenerator()->get_plugin_generator('mod_assign')->create_instance(
            ['course' => $course->id, 'name' => 'Ensayo personal']);
        $this->setUser($student);
        $CFG->local_acadassistant_rag_url = 'https://rag.example.test';
        $CFG->local_acadassistant_rag_shared_secret = str_repeat('a', 40);
        $state = ['topic' => ['intent' => 'academic', 'categories' => ['assignments'],
            'selected_assignment_id' => (int)$assignment->id,
            'scope_question' => 'Ensayo personal en Seminario']];
        $transport = function($url, $body) use (&$state, $assignment): array {
            $payload = json_decode($body, true);
            if (str_ends_with($url, '/interpret')) {
                $result = $state['topic'] + ['follow_up' => true, 'assignment_filter' => 'all'];
            } else {
                $this->assertSame([(int)$assignment->id],
                    array_column($payload['academic_context']['assignments'], 'assignment_id'));
                $result = ['answer' => 'Respuesta válida.', 'sources' => []];
            }
            return ['status' => 200, 'body' => json_encode($result)];
        };
        $assistant = new \local_acadassistant\local\academic_assistant($transport);
        for ($i = 0; $i < 6; $i++) {
            $response = $assistant->ask('¿Y a qué hora?', [], 0, [], $state);
            $state = $response['semantic_state'];
            $this->assertSame('Ensayo personal en Seminario', $state['topic']['scope_question']);
            $this->assertSame((int)$assignment->id, $state['topic']['selected_assignment_id']);
        }
    }

    public function test_proposed_operation_reads_only_enrolled_visible_assignments(): void {
        global $CFG;
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['fullname' => 'Seminario']);
        $private = $this->getDataGenerator()->create_course(['fullname' => 'Reservado']);
        $student = $this->getDataGenerator()->create_user();
        $this->getDataGenerator()->enrol_user($student->id, $course->id, 'student');
        $generator = $this->getDataGenerator()->get_plugin_generator('mod_assign');
        $assignment = $generator->create_instance(['course' => $course->id, 'name' => 'Ensayo']);
        require_once($CFG->dirroot . '/mod/assign/locallib.php');
        $cm = get_coursemodule_from_instance('assign', $assignment->id);
        $assign = new \assign(\context_module::instance($cm->id), $cm, $course);
        $assign->get_user_submission($student->id, true);
        $generator->create_instance(['course' => $private->id, 'name' => 'Secreto']);
        $this->setUser($student);
        $provider = new \local_acadassistant\local\academic_context_provider();
        $result = $provider->collect_for_plan(['intent' => 'weekly_plan', 'categories' => ['assignments'],
            'scope_question' => 'mis tareas pendientes']);
        $this->assertSame(['Ensayo'], array_column($result['academic_context']['assignments'], 'name'));
        $this->assertSame('not_submitted', $result['academic_context']['assignments'][0]['status']);
        $denied = $provider->collect_for_plan(['intent' => 'academic', 'categories' => ['assignments'],
            'scope_question' => 'tareas en Reservado']);
        $this->assertArrayNotHasKey('assignments', $denied['academic_context']);
        $this->assertNotEmpty($denied['academic_context']['query']['notices']);
    }

    public function test_social_skips_readers_and_weekly_reads_all_pages_before_asking_availability(): void {
        global $CFG;
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course();
        $student = $this->getDataGenerator()->create_user();
        $this->getDataGenerator()->enrol_user($student->id, $course->id, 'student');
        $generator = $this->getDataGenerator()->get_plugin_generator('mod_assign');
        for ($i = 0; $i < 25; $i++) {
            $generator->create_instance(['course' => $course->id, 'name' => 'Trabajo ' . $i]);
        }
        $this->setUser($student);
        $CFG->local_acadassistant_rag_url = 'https://rag.example.test';
        $CFG->local_acadassistant_rag_shared_secret = str_repeat('a', 40);
        $social = true;
        $transport = function($url, $body) use (&$social): array {
            $payload = json_decode($body, true);
            if (str_ends_with($url, '/interpret')) {
                $result = $social ? ['intent' => 'social', 'social' => 'greeting'] :
                    ['intent' => 'weekly_plan', 'categories' => ['assignments'], 'scope_question' => 'mis tareas'];
            } else {
                if ($social) {
                    $this->assertEmpty($payload['academic_context']);
                } else {
                    $this->assertCount(25, $payload['academic_context']['assignments']);
                    $this->assertFalse($payload['academic_context']['query']['has_more']);
                    $this->assertTrue($payload['academic_context']['query']['complete']);
                }
                $result = ['answer' => 'Respuesta válida.', 'sources' => []];
            }
            return ['status' => 200, 'body' => json_encode($result)];
        };
        $assistant = new \local_acadassistant\local\academic_assistant($transport);
        $greeting = $assistant->ask('hola');
        $this->assertEmpty($greeting['academic_provenance']);
        $social = false;
        $weekly = $assistant->ask('organiza mi semana');
        $this->assertSame(['academic'], $weekly['academic_provenance']);
    }

    public function test_pending_task_choices_bind_ids_and_revalidate_native_access(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course(['fullname' => 'Seminario']);
        $user = $this->getDataGenerator()->create_user();
        $this->getDataGenerator()->enrol_user($user->id, $course->id, 'student');
        $generator = $this->getDataGenerator()->get_plugin_generator('mod_assign');
        $first = $generator->create_instance(['course' => $course->id, 'name' => 'Ensayo personal']);
        $generator->create_instance(['course' => $course->id, 'name' => 'Informe práctico']);
        $this->setUser($user);
        $provider = new \local_acadassistant\local\academic_context_provider();
        $ambiguous = $provider->collect_for_plan(['intent' => 'academic', 'categories' => ['assignments'],
            'scope_question' => 'mis tareas', 'ambiguous_task' => true]);
        $this->assertCount(2, $ambiguous['task_choices']);
        $this->assertContains((int)$first->id, array_column($ambiguous['task_choices'], 'assignment_id'));
        $selectedplan = ['intent' => 'academic', 'categories' => ['assignments'],
            'scope_question' => 'mis tareas', 'assignment_filter' => 'all',
            'selected_assignment_id' => (int)$first->id];
        $selected = $provider->collect_for_plan($selectedplan);
        $this->assertSame([(int)$first->id], array_column($selected['academic_context']['assignments'], 'assignment_id'));
        $wrongperson = $provider->collect_for_plan(array_replace($selectedplan,
            ['selected_participant_name' => 'Otra persona']));
        $this->assertArrayNotHasKey('assignments', $wrongperson['academic_context']);
        $this->assertNotEmpty($wrongperson['academic_context']['query']['notices']);
        $gone = $provider->collect_for_plan(array_replace($selectedplan, ['selected_assignment_id' => 2147483647]));
        $this->assertArrayNotHasKey('assignments', $gone['academic_context']);
        $this->assertNotEmpty($gone['academic_context']['query']['notices']);
        $this->setUser($this->getDataGenerator()->create_user());
        $denied = $provider->collect_for_plan($selectedplan);
        $this->assertArrayNotHasKey('assignments', $denied['academic_context']);
        $this->assertNotEmpty($denied['academic_context']['query']['notices']);
    }

    public function test_current_named_task_overrides_a_broad_proposed_scope(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course();
        $user = $this->getDataGenerator()->create_user();
        $this->getDataGenerator()->enrol_user($user->id, $course->id, 'student');
        $generator = $this->getDataGenerator()->get_plugin_generator('mod_assign');
        foreach (['Ensayo personal', 'Informe práctico'] as $name) {
            $generator->create_instance(['course' => $course->id, 'name' => $name]);
        }
        $this->setUser($user);
        $result = (new \local_acadassistant\local\academic_context_provider())->collect_for_plan(
            ['intent' => 'academic', 'categories' => ['assignments'], 'scope_question' => 'mis tareas'],
            [], 0, [], 'Ensayo personal');
        $this->assertSame(['Ensayo personal'], array_column($result['academic_context']['assignments'], 'name'));
        $this->assertStringContainsString('Ensayo personal', $result['context_question']);
    }

    public function test_current_named_course_overrides_a_broad_or_stale_proposed_scope(): void {
        $this->resetAfterTest();
        $first = $this->getDataGenerator()->create_course(['fullname' => 'Algebra 101']);
        $second = $this->getDataGenerator()->create_course(['fullname' => 'Biologia 102']);
        $private = $this->getDataGenerator()->create_course(['fullname' => 'Reservado 103']);
        $user = $this->getDataGenerator()->create_user();
        foreach ([$first, $second] as $course) {
            $this->getDataGenerator()->enrol_user($user->id, $course->id, 'student');
        }
        $this->setUser($user);
        $provider = new \local_acadassistant\local\academic_context_provider();
        foreach (['mis cursos', 'cursos de Algebra 101'] as $scope) {
            $result = $provider->collect_for_plan(
                ['intent' => 'academic', 'categories' => ['courses'], 'scope_question' => $scope],
                [], 0, [], '¿Y en Biologia 102?');
            $this->assertSame([(int)$second->id], array_column($result['academic_context']['courses'], 'course_id'));
            $this->assertStringContainsString('Biologia 102', $result['context_question']);
            $this->assertStringNotContainsString('Algebra 101', $result['context_question']);
        }
        $denied = $provider->collect_for_plan(
            ['intent' => 'academic', 'categories' => ['courses'], 'scope_question' => 'mis cursos'],
            [], 0, [], '¿Y en Reservado 103?');
        $this->assertArrayNotHasKey('courses', $denied['academic_context']);
        $this->assertNotEmpty($denied['academic_context']['query']['notices']);
        $unknown = $provider->collect_for_plan(
            ['intent' => 'academic', 'categories' => ['courses'], 'scope_question' => 'mis cursos'],
            [], 0, [], '¿Y en el curso Desconocido 999?');
        $this->assertArrayNotHasKey('courses', $unknown['academic_context']);
        $this->assertNotEmpty($unknown['academic_context']['query']['notices']);
    }

    public function test_model_resolved_global_scope_does_not_inherit_an_old_course(): void {
        $this->resetAfterTest();
        $first = $this->getDataGenerator()->create_course(['fullname' => 'Algebra']);
        $second = $this->getDataGenerator()->create_course(['fullname' => 'Biologia']);
        $user = $this->getDataGenerator()->create_user();
        foreach ([$first, $second] as $course) {
            $this->getDataGenerator()->enrol_user($user->id, $course->id, 'student');
        }
        $this->setUser($user);
        $result = (new \local_acadassistant\local\academic_context_provider())->collect_for_plan(
            ['intent' => 'academic', 'categories' => ['courses'], 'scope_question' => 'mis cursos', 'follow_up' => true],
            [['question' => 'mis profesores en Biologia', 'answer' => 'Docentes visibles.']]);
        $this->assertCount(2, $result['academic_context']['courses']);
    }

    public function test_schedule_followup_keeps_the_explicit_week(): void {
        global $CFG;
        $this->resetAfterTest();
        $this->setUser($this->getDataGenerator()->create_user());
        $CFG->local_acadassistant_rag_url = 'https://rag.example.test';
        $CFG->local_acadassistant_rag_shared_secret = str_repeat('a', 40);
        $transport = function($url, $body): array {
            if (str_ends_with($url, '/interpret')) {
                $result = ['intent' => 'weekly_plan', 'categories' => ['assignments'], 'follow_up' => true,
                    'availability' => ['days' => [1, 3], 'start_hour' => 14, 'end_hour' => 16]];
            } else {
                $payload = json_decode($body, true);
                $this->assertSame(1, $payload['conversation_plan']['week_offset']);
                $this->assertSame([1, 3], $payload['conversation_plan']['availability']['days']);
                $result = ['answer' => 'No hay pendientes.', 'sources' => []];
            }
            return ['status' => 200, 'body' => json_encode($result)];
        };
        $state = ['topic' => ['intent' => 'weekly_plan', 'categories' => ['assignments']], 'week_offset' => 1];
        (new \local_acadassistant\local\academic_assistant($transport))->ask('martes y jueves de 14 a 16', [], 0, [], $state);
    }

    public function test_interpreter_request_uses_server_clock_and_rejects_unpermitted_plan(): void {
        global $CFG;
        $this->resetAfterTest();
        $student = $this->getDataGenerator()->create_user(['timezone' => 'America/Lima']);
        $this->setUser($student);
        $CFG->local_acadassistant_rag_url = 'https://rag.example.test';
        $CFG->local_acadassistant_rag_shared_secret = str_repeat('a', 40);
        $calls = 0;
        $transport = function($url, $body, $headers) use (&$calls): array {
            $calls++;
            $this->assertStringEndsWith('/api/v1/chat/interpret', $url);
            $request = json_decode($body, true);
            $this->assertSame('America/Lima', $request['runtime']['timezone']);
            $this->assertLessThanOrEqual(2, abs(time() - $request['runtime']['now']));
            $this->assertStringStartsWith('Bearer ', $headers['Authorization']);
            return ['status' => 200, 'body' => json_encode(['intent' => 'academic', 'categories' => ['sql']])];
        };
        $client = \local_acadassistant\local\rag_client::from_current_user($transport);
        try {
            $client->interpret('hola como estás');
            $this->fail('An unpermitted operation must never reach a Moodle reader.');
        } catch (\moodle_exception $e) {
            $this->assertSame('ragrequestfailed', $e->errorcode);
        }
        $this->assertSame(1, $calls);
    }
}
