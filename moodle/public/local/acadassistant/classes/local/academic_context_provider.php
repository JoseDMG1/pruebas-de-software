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
    private const CALENDAR_DAYS_BACK = 30;
    private const CALENDAR_DAYS_AHEAD = 180;

    /**
     * Collect only the categories that match the current question.
     *
     * @return array{course_ids:int[], academic_context:array<string, array>}
     */
    public function collect_for_question(string $question): array {
        global $CFG, $USER;

        if (!isloggedin() || isguestuser() || empty($USER->id)) {
            throw new \moodle_exception('requirelogin', 'error');
        }

        require_once($CFG->dirroot . '/mod/assign/locallib.php');
        require_once($CFG->libdir . '/gradelib.php');
        require_once($CFG->dirroot . '/calendar/lib.php');

        $courses = $this->accessible_courses($question);
        $courseids = array_map(static fn($course): int => (int)$course->id, $courses);
        $requested = $this->requested_categories($question);
        $context = [];

        if (in_array('courses', $requested, true)) {
            $context['courses'] = array_map(static function($course): array {
                return [
                    'course_id' => (int)$course->id,
                    'name' => (string)$course->fullname,
                    'short_name' => (string)$course->shortname,
                    'starts_at' => (int)$course->startdate,
                    'ends_at' => (int)$course->enddate,
                    'source' => 'Moodle',
                ];
            }, array_slice($courses, 0, self::MAX_RECORDS_PER_CATEGORY));
        }

        if (array_intersect($requested, ['assignments', 'grades'])) {
            [$assignments, $grades] = $this->assignment_and_grade_context($courses, $question, $requested);
            if (in_array('assignments', $requested, true)) {
                $context['assignments'] = $assignments;
            }
            if (in_array('grades', $requested, true)) {
                $context['grades'] = $grades;
            }
        }

        if (in_array('calendar', $requested, true)) {
            $context['calendar'] = $this->calendar_context($courseids);
        }

        return ['course_ids' => $courseids, 'academic_context' => $context];
    }

    /** Return courses Moodle permits this user to access, optionally narrowed by course name. */
    private function accessible_courses(string $question): array {
        global $USER, $DB;

        $courses = enrol_get_users_courses(
            $USER->id,
            true,
            'id, fullname, shortname, startdate, enddate',
            'fullname ASC'
        );
        $capabilitycourses = get_user_capability_course(
            'moodle/course:view',
            $USER->id,
            false,
            'fullname, shortname, startdate, enddate',
            'fullname ASC',
            self::MAX_COURSES
        );
        foreach ((array)$capabilitycourses as $course) {
            $courses[$course->id] = $course;
        }

        $accessible = [];
        foreach ($courses as $courseid => $course) {
            if ((int)$courseid === SITEID || count($accessible) >= self::MAX_COURSES) {
                continue;
            }
            $course = $DB->get_record('course', ['id' => $courseid]);
            if ($course && can_access_course($course, $USER, '', true)) {
                $accessible[$course->id] = $course;
            }
        }
        uasort($accessible, static fn($left, $right): int => strcasecmp($left->fullname, $right->fullname));

        $normalisedquestion = $this->normalise_text($question);
        $matched = [];
        foreach ($accessible as $course) {
            foreach ([$course->fullname, $course->shortname] as $name) {
                $normalisedname = $this->normalise_text((string)$name);
                if (strlen($normalisedname) >= 3 && str_contains($normalisedquestion, $normalisedname)) {
                    $matched[$course->id] = $course;
                    break;
                }
            }
        }
        if ($matched) {
            return $matched;
        }
        $namesunknowncourse = preg_match(
            '/\b(?:en|del|para)\s+(?:el\s+)?curso\s+[^?.,;]+/u',
            $normalisedquestion
        ) || preg_match(
            '/\b(?:en|del|para)\s+(?:el\s+)?\p{Lu}[\p{L}\p{N}-]*(?:\s+\p{Lu}[\p{L}\p{N}-]*)*/u',
            $question
        );
        return $namesunknowncourse ? [] : $accessible;
    }

    /** Read visible assignments and grades without creating or updating Moodle records. */
    private function assignment_and_grade_context(array $courses, string $question, array $requested): array {
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
                    if (in_array($field, ['duedate', 'cutoffdate', 'allowsubmissionsfromdate'], true)) {
                        $instance->{$field} = $value;
                    }
                }

                if ($wantsassignments && count($assignments) < self::MAX_RECORDS_PER_CATEGORY) {
                    $submission = $instance->teamsubmission
                        ? $assign->get_group_submission($target['id'], 0, false)
                        : $assign->get_user_submission($target['id'], false);
                    $duedate = (int)$instance->duedate;
                    $assignments[] = [
                        'course_id' => (int)$course->id,
                        'course_name' => (string)$course->fullname,
                        'assignment_id' => (int)$instance->id,
                        'name' => (string)$cm->name,
                        'due_at' => $duedate > 0 ? $duedate : null,
                        'status' => $submission ? (string)$submission->status : 'not_submitted',
                        'participant' => $target['name'],
                        'source' => 'Moodle',
                    ];
                }

            }

            if ($wantsgrades && count($grades) < self::MAX_RECORDS_PER_CATEGORY) {
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
            'u.id, u.firstname, u.lastname',
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
            if (count($grades) >= self::MAX_RECORDS_PER_CATEGORY || $gradeitem->itemtype !== 'mod') {
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
        foreach (array_slice($events, 0, self::MAX_RECORDS_PER_CATEGORY) as $event) {
            $result[] = [
                'event_id' => (int)$event->id,
                'course_id' => (int)$event->courseid,
                'name' => clean_param((string)$event->name, PARAM_TEXT),
                'starts_at' => (int)$event->timestart,
                'duration_seconds' => (int)$event->timeduration,
                'source' => 'Calendario Moodle',
            ];
        }
        return $result;
    }

    /** Choose only data categories suggested by the user's question. */
    private function requested_categories(string $question): array {
        $question = $this->normalise_text($question);
        $categories = [];
        if (preg_match('/\b(cursos?|llevo|matriculad[oa]s?|inscrit[oa]s?)\b/u', $question)) {
            $categories[] = 'courses';
        }
        if (preg_match(
            '/\b(tareas?|actividades?|entregas?|entregad[oa]s?|entregar|presentar|subir|'
                . 'pendientes?|faltantes?|atrasad[oa]s?|vencen|vencimiento|plazos?)\b/u',
            $question
        )) {
            $categories[] = 'assignments';
        }
        if (preg_match('/\b(calificaciones?|calificadas?|notas?|promedios?|puntajes?)\b/u', $question)) {
            $categories[] = 'grades';
        }
        if (preg_match(
            '/\b(calendario|eventos?|fechas?|cuando|inicia|empieza|comienza|ciclo|examen(?:es)?)\b/u',
            $question
        )) {
            $categories[] = 'calendar';
        }
        return $categories;
    }

    /** Lowercase and collapse whitespace for safe exact phrase matching. */
    private function normalise_text(string $text): string {
        $ascii = iconv('UTF-8', 'ASCII//TRANSLIT//IGNORE', $text);
        $normalised = \core_text::strtolower($ascii === false ? $text : $ascii);
        return trim(preg_replace('/\s+/', ' ', $normalised) ?? '');
    }
}
