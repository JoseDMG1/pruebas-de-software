<?php
// This file is part of Moodle - http://moodle.org/
// Licensed under the GNU General Public License version 3 or later.
namespace local_acadassistant\local;
defined('MOODLE_INTERNAL') || die();

/** Validate a proposed interpretation before any native Moodle read. */
final class conversation_plan {
    public static function validate(array $input): array {
        $defaults = ['intent' => '', 'social' => 'none', 'categories' => [], 'course_mode' => 'enrolled',
            'assignment_filter' => 'pending', 'scope_question' => '', 'document_question' => '',
            'follow_up' => false, 'teacher_confirmation' => false, 'teacher_reference' => '', 'ambiguous_task' => false,
            'finance' => false, 'blocked_part' => false, 'availability' => null,
            'availability_unknown' => false, 'week_offset' => 0, 'week_explicit' => false, 'week_start' => '',
            'priority' => [], 'clarification' => 'intent'];
        if (array_diff(array_keys($input), array_keys($defaults))) {
            self::invalid();
        }
        $plan = array_replace($defaults, $input);
        foreach (['intent' => ['social', 'capabilities', 'academic', 'document', 'weekly_plan', 'clarify', 'blocked'],
            'social' => ['none', 'greeting', 'thanks', 'bye'], 'course_mode' => ['enrolled', 'accessible', 'teaching'],
            'assignment_filter' => ['pending', 'submitted', 'all'],
            'clarification' => ['intent', 'course', 'task', 'week', 'availability', 'requests']] as $key => $values) {
            if (!in_array($plan[$key], $values, true)) {
                self::invalid();
            }
        }
        foreach (['follow_up', 'teacher_confirmation', 'ambiguous_task', 'finance', 'blocked_part',
            'availability_unknown', 'week_explicit'] as $key) {
            if (!is_bool($plan[$key])) {
                self::invalid();
            }
        }
        foreach (['scope_question', 'document_question', 'week_start', 'teacher_reference'] as $key) {
            if (!is_string($plan[$key]) || \core_text::strlen($plan[$key]) > ($key === 'week_start' ? 10 : ($key === 'teacher_reference' ? 200 : 1000))) {
                self::invalid();
            }
        }
        if (!in_array($plan['week_offset'], [0, 1], true) ||
                ($plan['week_start'] !== '' && (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $plan['week_start']) ||
                    !checkdate((int)substr($plan['week_start'], 5, 2), (int)substr($plan['week_start'], 8, 2),
                        (int)substr($plan['week_start'], 0, 4))))) {
            self::invalid();
        }
        if (!is_array($plan['categories']) || count($plan['categories']) > 5 ||
                array_diff($plan['categories'], ['courses', 'teachers', 'assignments', 'grades', 'calendar']) ||
                count(array_unique($plan['categories'])) !== count($plan['categories'])) {
            self::invalid();
        }
        if (!is_array($plan['priority']) || count($plan['priority']) > 20) {
            self::invalid();
        }
        foreach ($plan['priority'] as $name) {
            if (!is_string($name) || trim($name) === '' || \core_text::strlen($name) > 200) {
                self::invalid();
            }
        }
        if (in_array($plan['intent'], ['social', 'capabilities', 'blocked', 'clarify'], true) &&
                ($plan['categories'] || $plan['document_question'] !== '')) {
            self::invalid();
        }
        if (($plan['intent'] === 'social' && $plan['social'] === 'none') ||
                ($plan['intent'] === 'academic' && !$plan['categories']) ||
                ($plan['intent'] === 'document' && trim($plan['document_question']) === '') ||
                ($plan['intent'] === 'weekly_plan' && ($plan['categories'] !== ['assignments'] ||
                    $plan['assignment_filter'] !== 'pending' || $plan['document_question'] !== ''))) {
            self::invalid();
        }
        if ($plan['availability'] !== null) {
            $a = $plan['availability'];
            if (!is_array($a) || count($a) !== 3 || array_diff(array_keys($a), ['days', 'start_hour', 'end_hour']) ||
                    !is_array($a['days'] ?? null) || !count($a['days']) || count($a['days']) > 7 ||
                    count(array_unique($a['days'])) !== count($a['days']) ||
                    !is_int($a['start_hour'] ?? null) || !is_int($a['end_hour'] ?? null) ||
                    $a['start_hour'] < 0 || $a['end_hour'] > 24 || $a['end_hour'] <= $a['start_hour']) {
                self::invalid();
            }
            foreach ($a['days'] as $day) {
                if (!is_int($day) || $day < 0 || $day > 6) {
                    self::invalid();
                }
            }
        }
        return $plan;
    }

    private static function invalid(): never {
        throw new \moodle_exception('ragrequestfailed', 'local_acadassistant');
    }
}
