<?php
// This file is part of Moodle - http://moodle.org/
// Licensed under the GNU General Public License version 3 or later.
namespace local_acadassistant;
defined('MOODLE_INTERNAL') || die();

use local_acadassistant\local\academic_context_provider;
use local_acadassistant\local\academic_navigation;
use local_acadassistant\local\conversation_plan;

final class academic_navigation_test extends \advanced_testcase {
    public function test_navigation_rejects_non_array_categories(): void {
        $this->expectException(\moodle_exception::class);
        conversation_plan::validate(['intent' => 'academic', 'navigation' => 'open',
            'categories' => 'assignments']);
    }

    private function plan(string $mode = 'nearest_deadline', string $course = 'enrolled'): array {
        return conversation_plan::validate(['intent' => 'academic', 'categories' => ['assignments'],
            'navigation' => $mode, 'scope_question' => 'mis tareas', 'course_mode' => $course,
            'assignment_filter' => $mode === 'grading' ? 'all' : 'pending']);
    }

    public function test_nearest_deadline_returns_all_ties_and_ignores_overdue_undated_and_hidden(): void {
        $this->resetAfterTest();
        $g = $this->getDataGenerator();
        $student = $g->create_user();
        $course = $g->create_course();
        $g->enrol_user($student->id, $course->id, 'student');
        $now = time();
        foreach ([['Primera', $now + 3600, 1], ['Empatada', $now + 3600, 1],
                ['Posterior', $now + 7200, 1], ['Vencida', $now - 10, 1],
                ['Sin fecha', 0, 1], ['Oculta', $now + 10, 0]] as [$name, $due, $visible]) {
            $g->get_plugin_generator('mod_assign')->create_instance([
                'course' => $course->id, 'name' => $name, 'duedate' => $due, 'visible' => $visible,
            ]);
        }
        $this->setUser($student);
        $plan = $this->plan();
        $context = (new academic_context_provider())->collect_for_plan($plan);
        $response = academic_navigation::respond($plan, $context['academic_context'], $now);
        $this->assertCount(2, $response['navigation_links']);
        $this->assertStringContainsString('comparten', $response['answer']);
        foreach ($response['navigation_links'] as $link) {
            $this->assertStringContainsString('/mod/assign/view.php?id=', $link['url']);
            $this->assertMatchesRegularExpression('/Primera|Empatada/', $link['label']);
        }
    }

    public function test_partial_scan_never_claims_a_global_nearest_deadline(): void {
        $plan = $this->plan();
        $result = academic_navigation::respond($plan, ['query' => ['complete' => false, 'has_more' => true]]);
        $this->assertSame([], $result['navigation_links']);
        $this->assertStringContainsString('No pude revisar todas', $result['answer']);
    }

    public function test_teacher_can_open_grading_but_student_cannot(): void {
        $this->resetAfterTest();
        $g = $this->getDataGenerator();
        $course = $g->create_course();
        $teacher = $g->create_user();
        $student = $g->create_user();
        $g->enrol_user($teacher->id, $course->id, 'editingteacher');
        $g->enrol_user($student->id, $course->id, 'student');
        $g->get_plugin_generator('mod_assign')->create_instance([
            'course' => $course->id, 'name' => 'Ensayo', 'duedate' => time() + DAYSECS,
        ]);
        $this->setUser($teacher);
        $plan = $this->plan('grading', 'teaching');
        $context = (new academic_context_provider())->collect_for_plan($plan);
        $response = academic_navigation::respond($plan, $context['academic_context']);
        $this->assertCount(1, $response['navigation_links']);
        $this->assertStringContainsString('action=grading', $response['navigation_links'][0]['url']);
        $this->setUser($student);
        $response = academic_navigation::respond($plan, $context['academic_context']);
        $this->assertSame([], $response['navigation_links']);
    }

    public function test_navigation_rechecks_hidden_activity_after_collection(): void {
        global $DB;
        $this->resetAfterTest();
        $g = $this->getDataGenerator();
        $student = $g->create_user();
        $course = $g->create_course();
        $g->enrol_user($student->id, $course->id, 'student');
        $activity = $g->get_plugin_generator('mod_assign')->create_instance([
            'course' => $course->id, 'name' => 'Entrega', 'duedate' => time() + DAYSECS,
        ]);
        $this->setUser($student);
        $plan = $this->plan();
        $context = (new academic_context_provider())->collect_for_plan($plan);
        $DB->set_field('course_modules', 'visible', 0, ['id' => $activity->cmid]);
        rebuild_course_cache($course->id, true);
        $response = academic_navigation::respond($plan, $context['academic_context']);
        $this->assertSame([], $response['navigation_links']);
    }
    public function test_only_local_native_links_are_stored(): void {
        global $CFG;
        $links = [
            ['url' => $CFG->wwwroot . '/mod/assign/view.php?id=12', 'label' => '<script>x</script>', 'detail' => ''],
            ['url' => 'javascript:alert(1)', 'label' => 'No', 'detail' => ''],
            ['url' => 'https://outside.invalid/mod/assign/view.php?id=12', 'label' => 'No', 'detail' => ''],
            ['url' => $CFG->wwwroot . '/mod/assign/view.php?id=12&action=delete', 'label' => 'No', 'detail' => ''],
        ];
        $safe = academic_navigation::safe_links($links);
        $this->assertCount(1, $safe);
        $html = $GLOBALS['OUTPUT']->render_from_template('local_acadassistant/chat', [
            'hasmessages' => true, 'messages' => [['answer' => 'Enlace', 'navigation_links' => $safe]],
        ]);
        $this->assertStringNotContainsString('<script>x</script>', $html);
        $this->assertStringContainsString('&lt;script&gt;', $html);
    }

    public function test_nearest_scans_later_pages_before_selecting(): void {
        global $CFG;
        $this->resetAfterTest();
        $g = $this->getDataGenerator();
        $course = $g->create_course();
        $student = $g->create_user();
        $g->enrol_user($student->id, $course->id, 'student');
        for ($i = 0; $i < 22; $i++) {
            $g->get_plugin_generator('mod_assign')->create_instance([
                'course' => $course->id, 'name' => 'Actividad ' . $i,
                'duedate' => time() + ($i === 21 ? DAYSECS : 2 * DAYSECS),
            ]);
        }
        $this->setUser($student);
        $CFG->local_acadassistant_rag_url = 'https://rag.example.test';
        $CFG->local_acadassistant_rag_shared_secret = str_repeat('x', 40);
        $plan = $this->plan();
        $transport = static function($url) use ($plan): array {
            if (!str_ends_with($url, '/interpret')) {
                throw new \RuntimeException('Navigation must resolve in Moodle.');
            }
            return ['status' => 200, 'body' => json_encode($plan)];
        };
        $result = (new \local_acadassistant\local\academic_assistant($transport))
            ->ask('Mándame a la entrega más próxima');
        $this->assertCount(1, $result['navigation_links']);
        $this->assertStringContainsString('Actividad 21', $result['navigation_links'][0]['label']);
    }
    public function test_gradebook_navigation_without_published_grades_respects_role(): void {
        $this->resetAfterTest();
        $g = $this->getDataGenerator();
        $course = $g->create_course();
        $teacher = $g->create_user();
        $student = $g->create_user();
        $outsider = $g->create_user();
        $g->enrol_user($teacher->id, $course->id, 'editingteacher');
        $g->enrol_user($student->id, $course->id, 'student');
        $plan = conversation_plan::validate(['intent' => 'academic', 'categories' => ['grades'],
            'navigation' => 'open', 'scope_question' => $course->fullname]);
        foreach ([[$teacher, '/grader/'], [$student, '/user/']] as [$user, $path]) {
            $this->setUser($user);
            $result = academic_navigation::respond($plan, [], null, [$course->id]);
            $this->assertCount(1, $result['navigation_links']);
            $this->assertStringContainsString($path, $result['navigation_links'][0]['url']);
        }
        $this->setUser($outsider);
        $result = academic_navigation::respond($plan, [], null, [$course->id]);
        $this->assertSame([], $result['navigation_links']);
    }

    public function test_individual_extension_changes_nearest_selection(): void {
        global $DB;
        $this->resetAfterTest();
        $g = $this->getDataGenerator();
        $student = $g->create_user();
        $course = $g->create_course();
        $g->enrol_user($student->id, $course->id, 'student');
        $now = time();
        $assignment = $g->get_plugin_generator('mod_assign')->create_instance([
            'course' => $course->id, 'name' => 'Con prórroga', 'duedate' => $now + DAYSECS,
        ]);
        $g->get_plugin_generator('mod_assign')->create_instance([
            'course' => $course->id, 'name' => 'Más cercana', 'duedate' => $now + 2 * DAYSECS,
        ]);
        $DB->insert_record('assign_user_flags', (object)[
            'assignment' => $assignment->id, 'userid' => $student->id,
            'extensionduedate' => $now + 3 * DAYSECS,
        ]);
        $this->setUser($student);
        $plan = $this->plan();
        $context = (new academic_context_provider())->collect_for_plan($plan);
        $response = academic_navigation::respond($plan, $context['academic_context'], $now);
        $this->assertCount(1, $response['navigation_links']);
        $this->assertStringContainsString('Más cercana', $response['navigation_links'][0]['label']);
    }
}
