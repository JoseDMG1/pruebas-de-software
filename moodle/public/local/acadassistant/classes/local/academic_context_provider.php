<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

namespace local_acadassistant\local;

defined('MOODLE_INTERNAL') || die();

/** Reads a bounded set of live Moodle data visible to the current user. */
final class academic_context_provider {
    private const MAX_COURSES = 500;
    private const MAX_RECORDS_PER_CATEGORY = 20;
    private int $recordlimit = 21;
    private bool $scopecomplete = true;
    private bool $scopeavailable = true;
    private const CALENDAR_DAYS_BACK = 30;
    private const CALENDAR_DAYS_AHEAD = 180;

    /**
     * Collect only the categories that match the current question.
     *
     * @return array{course_ids:int[], academic_context:array<string, array>, requested_categories:string[]}
     */
    public function collect_for_question(string $question, array $conversationcontext = [], int $offset = 0, array $seen = []): array {
        global $CFG, $USER;

        if (!isloggedin() || isguestuser() || empty($USER->id)) {
            throw new \moodle_exception('requirelogin', 'error');
        }

        require_once($CFG->dirroot . '/mod/assign/locallib.php');
        require_once($CFG->libdir . '/gradelib.php');
        require_once($CFG->dirroot . '/calendar/lib.php');

        $offset = max(0, min(10000, $offset));
        $this->recordlimit = $offset + count($seen) + self::MAX_RECORDS_PER_CATEGORY + 1;
        $this->scopecomplete = true;
        $this->scopeavailable = true;
        $plan = academic_question::interpret($question, $conversationcontext);
        $previousquestions = $plan['follow_up'] ? array_column(array_slice($conversationcontext, -2), 'question') : [];
        $courses = $this->accessible_courses($plan['scope_question'], $previousquestions);
        $academicavailable = $this->scopeavailable;
        $courseids = array_values(array_map(static fn($course): int => (int)$course->id, $courses));
        $documentcourseids = [];
        if ($plan['document_question'] !== '') {
            $documentcourses = $this->accessible_courses($plan['document_question'], $previousquestions);
            $documentcourseids = array_values(array_map(static fn($course): int => (int)$course->id, $documentcourses));
            $courseids = array_values(array_unique(array_merge($courseids, $documentcourseids)));
        }
        $requested = $plan['categories'];
        $context = [];

        if (in_array('courses', $requested, true)) {
            $listedcourses = $this->courses_for_mode($courses, $plan['course_mode']);
            $context['courses'] = array_map(static function($course): array {
                return [
                    'course_id' => (int)$course->id,
                    'name' => (string)$course->fullname,
                    'short_name' => (string)$course->shortname,
                    'starts_at' => (int)$course->startdate,
                    'ends_at' => (int)$course->enddate,
                    'source' => 'Moodle',
                ];
            }, array_values($listedcourses));
        }

        $tasknames = [];
        if (array_intersect($requested, ['assignments', 'grades'])) {
            $tasknames = $this->selected_task_names($courses, array_merge([$question], array_reverse($previousquestions)));
            [$assignments, $grades] = $this->assignment_and_grade_context($courses, $question, $requested, $plan['assignment_filter'], $tasknames);
            if (in_array('assignments', $requested, true)) {
                $context['assignments'] = $assignments;
            }
            if (in_array('grades', $requested, true)) {
                $context['grades'] = $grades;
            }
        }

        if (in_array('teachers', $requested, true)) {
            $context['teachers'] = $this->teacher_context($this->courses_for_mode($courses, $plan['course_mode']));
        }

        if (in_array('calendar', $requested, true)) {
            $context['calendar'] = $this->calendar_context($courseids);
        }

        $notices = [];
        if ($plan['finance']) {
            $notices[] = 'El asistente todavía no consulta cuotas, saldos ni pagos personales.';
        }
        if ($requested && !$academicavailable) {
            $notices[] = 'No puedo consultar datos de ese curso con el acceso disponible. Precisa el curso que necesitas.';
            $context = [];
        }
        if ($plan['ambiguous_task'] && count($context['assignments'] ?? []) > 1) {
            $notices[] = '¿De cuál tarea necesitas la fecha? Indica su nombre y curso.';
            unset($context['assignments']);
        }
        $hasmore = false;
        $newseen = $seen;
        foreach ($context as $category => &$records) {
            $records = array_values($records);
            if ($seen) {
                $records = array_values(array_filter($records, static fn($record) =>
                    !in_array(self::record_key($category, $record), $seen, true)));
            }
            $hasmore = $hasmore || count($records) > ($seen ? 0 : $offset) + self::MAX_RECORDS_PER_CATEGORY;
            $records = array_slice($records, $seen ? 0 : $offset, self::MAX_RECORDS_PER_CATEGORY);
            foreach ($records as $record) {
                $newseen[] = self::record_key($category, $record);
            }
        }
        unset($records);
        $context['query'] = [
            'categories' => $requested, 'course_mode' => $plan['course_mode'],
            'assignment_filter' => $plan['assignment_filter'], 'has_more' => $hasmore,
            'teacher_confirmation' => $plan['teacher_confirmation'],
            'complete' => $this->scopecomplete, 'continuing' => (bool)$seen, 'notices' => $notices,
            'document_question' => $plan['document_question'],
            'document_course_ids' => $documentcourseids,
        ];
        return [
            'course_ids' => $courseids,
            'academic_context' => $context,
            'requested_categories' => $requested,
            'continuation_seen' => array_values(array_unique($newseen)),
            'context_question' => $this->resolved_question($question . ($tasknames ? ' (' . implode(', ', $tasknames) . ')' : ''), $plan, $courses),
        ];
    }

    /** Keep the interpreted operation across bounded follow-up chains and continuation. */
    private function resolved_question(string $question, array $plan, array $courses): string {
        if (!$plan['categories']) {
            return $question;
        }
        $names = ['courses' => match ($plan['course_mode']) {
            'enrolled' => 'mis cursos', 'accessible' => 'cursos que puedo consultar', 'teaching' => 'cursos que enseño',
        }, 'teachers' => 'mis profesores', 'grades' => 'calificaciones', 'calendar' => 'calendario',
            'assignments' => match ($plan['assignment_filter']) {
                'pending' => 'tareas pendientes', 'submitted' => 'tareas entregadas', 'all' => 'todas las tareas',
            }];
        $operations = array_map(static fn($category) => $names[$category], $plan['categories']);
        // A single narrowed course keeps a reference without narrowing a global multi-course question.
        $scope = count($courses) === 1 ? ' en ' . reset($courses)->fullname : '';
        return \core_text::substr(implode(' y ', $operations) . $scope . ': ' . $question, 0, 1000);
    }

    /** Stable identities for continuation; changing a due date does not repeat an activity. */
    private static function record_key(string $category, array $record): string {
        $identity = match ($category) {
            'courses' => $record['course_id'],
            'assignments' => $record['assignment_id'],
            'calendar' => $record['event_id'],
            'grades' => [$record['course_id'], $record['item_name'], $record['participant']],
            'teachers' => [$record['course_id'], $record['teacher_id'] ?? null, $record['names']],
        };
        return $category . ':' . hash('sha256', json_encode($identity));
    }

    /** Membership and course-local teaching roles are independent of global access. */
    private function courses_for_mode(array $courses, string $mode): array {
        global $USER;
        if ($mode === 'accessible') {
            return $courses;
        }
        $enrolled = enrol_get_users_courses($USER->id, true);
        $teacherroles = get_archetype_roles('teacher') + get_archetype_roles('editingteacher');
        return array_filter($courses, static function($course) use ($USER, $mode, $enrolled, $teacherroles): bool {
            if (!isset($enrolled[$course->id])) {
                return false;
            }
            if ($mode === 'enrolled') {
                return true;
            }
            foreach (get_user_roles(\context_course::instance($course->id), $USER->id, false) as $role) {
                if (isset($teacherroles[$role->roleid])) {
                    return true;
                }
            }
            return false;
        });
    }

    /** Use Moodle's participants search, including hidden roles and compulsory group filters. */
    private function teacher_context(array $courses): array {
        global $CFG, $USER;
        require_once($CFG->dirroot . '/course/lib.php');
        $roles = get_archetype_roles('teacher') + get_archetype_roles('editingteacher');
        $result = [];
        foreach ($courses as $course) {
            $context = \context_course::instance($course->id);
            $names = [];
            $allowed = course_can_view_participants($context);
            if ($course->groupmode == SEPARATEGROUPS && !has_capability('moodle/site:accessallgroups', $context)
                    && !groups_get_all_groups($course->id, $USER->id)) {
                $allowed = false;
            }
            if ($allowed && $roles) {
                $filters = new \core_user\table\participants_filterset();
                $filterclass = \core_table\local\filter\integer_filter::class;
                $jointype = \core_table\local\filter\filter::JOINTYPE_DEFAULT;
                $filters->add_filter(new $filterclass('courseid', $jointype, [(int)$course->id]));
                $filters->add_filter(new $filterclass('roles', $jointype, array_map('intval', array_keys($roles))));
                $search = new \core_user\table\participants_search($course, $context, $filters);
                $participants = $search->get_participants(sort: 'id ASC');
                foreach ($participants as $participant) {
                    if (is_enrolled($context, $participant->id, '', true)) {
                        $names[(int)$participant->id] = fullname($participant, has_capability('moodle/site:viewfullnames', $context));
                    }
                }
                $participants->close();
            }
            foreach ($names ?: [0 => ''] as $teacherid => $name) {
            $result[] = ['course_id' => (int)$course->id, 'course_name' => $course->fullname,
                'names' => $name === '' ? [] : [$name], 'teacher_id' => $teacherid ? (int)$teacherid : null,
                'state' => $allowed ? 'ok' : 'unavailable',
                'source' => 'Moodle'];
            }
        }
        return $result;
    }

    /** Return courses Moodle permits this user to access, optionally narrowed by course name. */
    private function accessible_courses(string $question, array $previousquestions = []): array {
        global $USER, $DB;

        // Resolve an explicit course before applying the broad-scope request bound.
        // Catalog names never become evidence until native access has been checked.
        $normalisedquestion = $this->normalise_text($question);
        $catalog = $DB->get_recordset('course', null, 'id ASC', 'id, fullname, shortname');
        $named = [];
        $namesfound = false;
        foreach ($catalog as $candidate) {
            if ((int)$candidate->id === (int)SITEID) {
                continue;
            }
            foreach ([$candidate->fullname, $candidate->shortname] as $name) {
                $normalisedname = $this->normalise_text($name);
                if (strlen($normalisedname) >= 3 && str_contains($normalisedquestion, $normalisedname)) {
                    $namesfound = true;
                    $course = get_course($candidate->id);
                    if (can_access_course($course, $USER, '', true)) {
                        $named[$course->id] = $course;
                    }
                    break;
                }
            }
        }
        $catalog->close();
        if ($namesfound) {
            $this->scopeavailable = (bool)$named;
            return $named;
        }

        $courses = enrol_get_users_courses(
            $USER->id,
            true,
            'id, fullname, shortname, startdate, enddate',
            'fullname ASC'
        );
        $capabilitycourses = get_user_capability_course(
            'moodle/course:view',
            $USER->id,
            true,
            'fullname, shortname, startdate, enddate',
            'fullname ASC',
            self::MAX_COURSES + 2
        );
        foreach ($capabilitycourses ?: [] as $course) {
            $courses[$course->id] = $course;
        }

        $accessible = [];
        foreach ($courses as $courseid => $course) {
            if ((int)$courseid === (int)SITEID) {
                continue;
            }
            if (count($accessible) >= self::MAX_COURSES) {
                $this->scopecomplete = false;
                continue;
            }
            $course = $DB->get_record('course', ['id' => $courseid]);
            if ($course && can_access_course($course, $USER, '', true)) {
                $accessible[$course->id] = $course;
            }
        }
        uasort($accessible, static fn($left, $right): int =>
            strcasecmp($left->fullname, $right->fullname) ?: ((int)$left->id <=> (int)$right->id));

        $normalisedquestion = $this->normalise_text($question);
        $namesunknowncourse = preg_match(
            '/\b(?:en|del|para)\s+(?:el\s+)?curso\s+[^?.,;]+/u',
            $normalisedquestion
        ) || preg_match(
            '/\b(?:en|del|para)\s+(?:el\s+)?\p{Lu}[\p{L}\p{N}-]*(?:\s+\p{Lu}[\p{L}\p{N}-]*)*/u',
            $question
        );
        if ($namesunknowncourse) {
            $this->scopeavailable = false;
            return [];
        }
        foreach (array_reverse($previousquestions) as $previousquestion) {
            $normalisedprevious = $this->normalise_text($previousquestion);
            $previousmatches = [];
            foreach ($accessible as $course) {
                foreach ([$course->fullname, $course->shortname] as $name) {
                    $normalisedname = $this->normalise_text((string)$name);
                    if (strlen($normalisedname) >= 3 && str_contains($normalisedprevious, $normalisedname)) {
                        $previousmatches[$course->id] = $course;
                        break;
                    }
                }
            }
            if ($previousmatches) {
                return $previousmatches;
            }
        }
        return $accessible;
    }

    /** Resolve named visible tasks before pagination, preferring the current question over its topic. */
    private function selected_task_names(array $courses, array $questions): array {
        global $USER;
        foreach ($questions as $question) {
            $names = [];
            foreach ($courses as $course) {
                foreach (get_fast_modinfo($course, $USER->id)->get_instances_of('assign') as $cm) {
                    if ($cm->uservisible && has_capability('mod/assign:view', \context_module::instance($cm->id)) &&
                            str_contains(academic_question::normalise($question), academic_question::normalise($cm->name))) {
                        $names[] = (string)$cm->name;
                    }
                }
            }
            if ($names) {
                return array_values(array_unique($names));
            }
        }
        return [];
    }

    /** Read visible assignments and grades without creating or updating Moodle records. */
    private function assignment_and_grade_context(array $courses, string $question, array $requested, string $assignmentfilter, array $tasknames): array {
        global $USER;

        $assignments = [];
        $grades = [];
        $wantsassignments = in_array('assignments', $requested, true);
        $wantsgrades = in_array('grades', $requested, true);
        foreach ($courses as $course) {
            $coursecontext = \context_course::instance($course->id);
            $canviewallgrades = has_capability('moodle/grade:viewall', $coursecontext);
            $modinfo = get_fast_modinfo($course, $USER->id);
            $target = $this->participant_for_question(
                $course,
                $question,
                $canviewallgrades,
                $modinfo->get_instances_of('assign')
            );

            foreach ($modinfo->get_instances_of('assign') as $cm) {
                if (!$cm->uservisible || !has_capability('mod/assign:view', \context_module::instance($cm->id))) {
                    continue;
                }
                $assign = new \assign(\context_module::instance($cm->id), $cm, $course);
                if (!$this->can_view_submission($assign, $cm, $target['id'])) {
                    continue;
                }
                $instance = $assign->get_instance($target['id']);
                foreach ($assign->override_exists($target['id']) as $field => $value) {
                    if ($value !== null && in_array($field, ['duedate', 'cutoffdate', 'allowsubmissionsfromdate'], true)) {
                        $instance->{$field} = $value;
                    }
                }

                if ($wantsassignments && count($assignments) < $this->recordlimit &&
                        (!$tasknames || in_array((string)$cm->name, $tasknames, true))) {
                    $submission = $instance->teamsubmission
                        ? $assign->get_group_submission($target['id'], 0, false)
                        : $assign->get_user_submission($target['id'], false);
                    $flags = $assign->get_user_flags($target['id'], false);
                    $duedate = max((int)$instance->duedate, (int)($flags->extensionduedate ?? 0));
                    $submissionstatus = $submission ? (string)$submission->status : 'not_submitted';
                    $matchesfilter = $assignmentfilter;
                    if (($matchesfilter === 'pending' && $submissionstatus === 'submitted') ||
                            ($matchesfilter === 'submitted' && $submissionstatus !== 'submitted')) {
                        continue;
                    }
                    $assignments[] = [
                        'course_id' => (int)$course->id,
                        'course_name' => (string)$course->fullname,
                        'assignment_id' => (int)$instance->id,
                        'name' => (string)$cm->name,
                        'due_at' => $duedate > 0 ? $duedate : null,
                        'due_date' => $duedate > 0 ? userdate($duedate, '%Y-%m-%d %H:%M') : null,
                        'status' => $submission ? (string)$submission->status : 'not_submitted',
                        'participant' => $target['name'],
                        'source' => 'Moodle',
                    ];
                }

            }

            if ($wantsgrades && count($grades) < $this->recordlimit) {
                $this->append_visible_module_grades($grades, $course, $modinfo, $target);
            }
        }
        return [$assignments, $grades];
    }

    /** Resolve a named participant only within a course where Moodle grants grade visibility. */
    private function participant_for_question(
        \stdClass $course,
        string $question,
        bool $canviewallgrades,
        array $assignments
    ): array {
        global $USER;

        $current = ['id' => (int)$USER->id, 'name' => null];
        if (!$canviewallgrades) {
            foreach ($assignments as $cm) {
                $assign = new \assign(\context_module::instance($cm->id), $cm, $course);
                if ($assign->can_view_grades()) {
                    $canviewallgrades = true;
                    break;
                }
            }
        }
        if (!$canviewallgrades) {
            return $current;
        }

        $question = $this->normalise_text($question);
        $matches = [];
        foreach (get_enrolled_users(
            \context_course::instance($course->id),
            '',
            0,
            'u.id, ' . implode(', ', array_map(
                static fn($field) => 'u.' . $field,
                \core_user\fields::get_name_fields()
            )),
            'u.id ASC',
            0,
            self::MAX_COURSES,
            true
        ) as $user) {
            if ((int)$user->id === (int)$USER->id) {
                continue;
            }
            $visibleinactivity = false;
            foreach ($assignments as $cm) {
                $assign = new \assign(\context_module::instance($cm->id), $cm, $course);
                if ($assign->can_view_grades() && $this->can_view_submission($assign, $cm, $user->id)) {
                    $visibleinactivity = true;
                    break;
                }
            }
            if (!$visibleinactivity) {
                continue;
            }
            $fullname = fullname($user);
            $normalisedname = $this->normalise_text($fullname);
            if (strlen($normalisedname) > 3 && str_contains($question, $normalisedname)) {
                $matches[(int)$user->id] = ['id' => (int)$user->id, 'name' => $fullname];
            }
        }
        return count($matches) === 1 ? reset($matches) : $current;
    }

    /** Add visible grades for module items in a course gradebook. */
    private function append_visible_module_grades(
        array &$grades,
        \stdClass $course,
        \course_modinfo $modinfo,
        array $target
    ): void {
        foreach ((array)\grade_item::fetch_all(['courseid' => $course->id]) as $gradeitem) {
            if (count($grades) >= $this->recordlimit || $gradeitem->itemtype !== 'mod') {
                continue;
            }
            $instances = $modinfo->get_instances_of($gradeitem->itemmodule);
            $cm = $instances[$gradeitem->iteminstance] ?? null;
            if (!$cm || !$cm->uservisible || !$this->grade_is_visible($gradeitem, $target['id'], $course)) {
                continue;
            }
            if ($gradeitem->itemmodule === 'assign') {
                $assign = new \assign(\context_module::instance($cm->id), $cm, $course);
                if (!$this->can_view_submission($assign, $cm, $target['id'])) {
                    continue;
                }
            }
            $grade = $gradeitem->get_grade($target['id'], false);
            if (!$grade || $grade->finalgrade === null) {
                continue;
            }
            $grades[] = [
                'course_id' => (int)$course->id,
                'course_name' => (string)$course->fullname,
                'item_name' => (string)$gradeitem->get_name(),
                'grade' => (string)grade_format_gradevalue($grade->finalgrade, $gradeitem),
                'participant' => $target['name'],
                'source' => 'Moodle',
            ];
        }
    }

    /** Respect separate-group access as Moodle does for the activity's participants. */
    private function can_view_submission(\assign $assign, \cm_info $cm, int $userid): bool {
        global $USER;

        if (!$assign->can_view_submission($userid)) {
            return false;
        }
        if ($userid === (int)$USER->id || $cm->effectivegroupmode !== SEPARATEGROUPS ||
                has_capability('moodle/site:accessallgroups', \context_module::instance($cm->id))) {
            return true;
        }
        $usergroups = groups_get_activity_allowed_groups($cm, $userid);
        $allowedgroups = groups_get_activity_allowed_groups($cm, $USER->id);
        return (bool)array_intersect(array_keys($usergroups), array_keys($allowedgroups));
    }

    /** Apply Moodle grade visibility and participant permissions without triggering regrading. */
    private function grade_is_visible(\grade_item $item, int $userid, \stdClass $course): bool {
        global $USER;

        $coursecontext = \context_course::instance($course->id);
        $canviewhidden = has_capability('moodle/grade:viewhidden', $coursecontext);
        if ($userid !== (int)$USER->id) {
            $allowed = has_capability('moodle/grade:viewall', $coursecontext);
            if (!$allowed && $item->itemmodule === 'assign') {
                $instances = get_fast_modinfo($course, $USER->id)->get_instances_of('assign');
                $cm = $instances[$item->iteminstance] ?? null;
                if ($cm) {
                    $assign = new \assign(\context_module::instance($cm->id), $cm, $course);
                    $allowed = $assign->can_view_submission($userid);
                }
            }
            if (!$allowed) {
                return false;
            }
        }
        if ($item->is_hidden() && !$canviewhidden) {
            return false;
        }
        $grade = $item->get_grade($userid, false);
        return $grade && (!$grade->is_hidden() || $canviewhidden);
    }

    /** Get visible personal, group, and authorized course calendar events. */
    private function calendar_context(array $courseids): array {
        global $USER;

        $groupids = [];
        foreach ($courseids as $courseid) {
            $groups = groups_get_user_groups($courseid, $USER->id);
            $groupids = array_merge($groupids, $groups[0] ?? []);
        }
        $groupids = array_values(array_unique(array_map('intval', $groupids)));
        $now = time();
        $events = calendar_get_events(
            $now - self::CALENDAR_DAYS_BACK * DAYSECS,
            $now + self::CALENDAR_DAYS_AHEAD * DAYSECS,
            [$USER->id, 0],
            $groupids ?: false,
            $courseids ?: false,
            true,
            true
        );
        $result = [];
        foreach (array_slice($events, 0, $this->recordlimit) as $event) {
            $result[] = [
                'event_id' => (int)$event->id,
                'course_id' => (int)$event->courseid,
                'name' => clean_param((string)$event->name, PARAM_TEXT),
                'starts_at' => (int)$event->timestart,
                'starts_date' => userdate((int)$event->timestart, '%Y-%m-%d %H:%M'),
                'duration_seconds' => (int)$event->timeduration,
                'source' => 'Calendario Moodle',
            ];
        }
        return $result;
    }

    /** Lowercase and collapse whitespace for safe exact phrase matching. */
    private function normalise_text(string $text): string {
        return academic_question::normalise($text);
    }
}
