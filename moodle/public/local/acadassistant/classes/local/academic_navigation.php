<?php
// This file is part of Moodle - http://moodle.org/
// Licensed under the GNU General Public License version 3 or later.
namespace local_acadassistant\local;
defined('MOODLE_INTERNAL') || die();

/** Resolve native destinations from current, authorized Moodle records. */
final class academic_navigation {
    public static function respond(array $plan, array $context, ?int $now = null, array $courseids = []): array {
        $now ??= time();
        $links = [];
        $choices = [];
        $nearest = $plan['navigation'] === 'nearest_deadline';
        $query = $context['query'] ?? [];
        if ($nearest && (!($query['complete'] ?? false) || ($query['has_more'] ?? false))) {
            return self::result('No pude revisar todas las tareas. Indica un curso para localizar la entrega más próxima.', []);
        }
        $rows = $context['assignments'] ?? [];
        if ($nearest) {
            $rows = array_values(array_filter($rows, static fn($row) =>
                !empty($row['due_at']) && $row['due_at'] >= $now &&
                ($plan['assignment_filter'] !== 'pending' || $row['status'] !== 'submitted')));
            if ($rows) {
                $deadline = min(array_column($rows, 'due_at'));
                $rows = array_values(array_filter($rows, static fn($row) => $row['due_at'] === $deadline));
            }
        }
        foreach ($rows as $row) {
            if (!can_access_course(get_course($row['course_id']))) {
                continue;
            }
            $cm = get_coursemodule_from_instance('assign', $row['assignment_id'], $row['course_id']);
            if (!$cm) {
                continue;
            }
            $modinfo = get_fast_modinfo($row['course_id']);
            $info = $modinfo->get_cm($cm->id);
            $modulecontext = \context_module::instance($cm->id);
            if (!$info->uservisible || !has_capability('mod/assign:view', $modulecontext)) {
                continue;
            }
            $params = ['id' => $cm->id];
            $label = $row['name'] . ' — ' . $row['course_name'];
            if ($plan['navigation'] === 'grading') {
                if (!has_capability('mod/assign:grade', $modulecontext)) {
                    continue;
                }
                $params['action'] = 'grading';
                $label = 'Calificar: ' . $label;
            }
            $url = (new \moodle_url('/mod/assign/view.php', $params))->out(false);
            $choices[$url] = array_intersect_key($row, array_flip([
                'assignment_id', 'course_id', 'name', 'course_name', 'participant',
            ]));
            $links[$url] = ['url' => $url, 'label' => $label,
                'detail' => $row['due_date'] ? 'Vence: ' . $row['due_date'] : 'Sin fecha de entrega'];
        }
        foreach ($context['courses'] ?? [] as $course) {
            $record = get_course($course['course_id']);
            if (!can_access_course($record)) {
                continue;
            }
            $url = (new \moodle_url('/course/view.php', ['id' => $record->id]))->out(false);
            $links[$url] = ['url' => $url, 'label' => $course['name'], 'detail' => 'Abrir curso'];
        }
        $gradecourses = in_array('grades', $plan['categories'], true)
            ? array_unique(array_merge($courseids, array_column($context['grades'] ?? [], 'course_id'))) : [];
        foreach ($gradecourses as $courseid) {
            if (!can_access_course(get_course($courseid))) {
                continue;
            }
            $ctx = \context_course::instance($courseid);
            $viewall = has_capability('moodle/grade:viewall', $ctx);
            $reportcapability = $viewall ? 'gradereport/grader:view' : 'gradereport/user:view';
            if ((!$viewall && !has_capability('moodle/grade:view', $ctx)) ||
                    !has_capability($reportcapability, $ctx)) {
                continue;
            }
            $path = $viewall ? '/grade/report/grader/index.php' : '/grade/report/user/index.php';
            $url = (new \moodle_url($path, ['id' => $courseid]))->out(false);
            $links[$url] = ['url' => $url, 'label' => 'Calificaciones — ' . get_course($courseid)->fullname,
                'detail' => 'Abrir informe'];
        }
        if (in_array('calendar', $plan['categories'], true)) {
            $url = (new \moodle_url('/calendar/view.php', ['view' => 'upcoming']))->out(false);
            $links[$url] = ['url' => $url, 'label' => 'Calendario de Moodle', 'detail' => 'Próximos eventos'];
        }
        if (!$links) {
            return self::result($nearest
                ? 'No hay entregas pendientes con vencimiento futuro visible en los cursos consultados. Las vencidas o sin fecha no se consideran próximas.'
                : 'No encontré un destino disponible con tus permisos actuales. Indica el curso o la actividad que deseas abrir.', []);
        }
        $answer = $nearest
            ? (count($links) > 1 ? 'Estas actividades comparten el vencimiento más próximo.' : 'Esta es la actividad con el vencimiento más próximo.')
            : 'Puedes abrir los siguientes destinos de Moodle.';
        if (!$nearest && (($query['has_more'] ?? false) || !($query['complete'] ?? true))) {
            $answer .= ' La lista es parcial; puedes acotar por curso o continuar.';
        }
        $result = self::result($answer . "\n\nSegún los datos visibles de Moodle.", array_values($links));
        $result['navigation_choices'] = array_slice(array_values($choices), 0, 20);
        return $result;
    }

    /** Only native read-only destinations may be retained in the session. */
    public static function safe_links(array $links): array {
        global $CFG;
        $pattern = '~^' . preg_quote(rtrim($CFG->wwwroot, '/'), '~') .
            '/(?:(?:mod/assign/view\.php\?id=[1-9][0-9]*(?:&action=grading)?)|' .
            '(?:course/view\.php\?id=[1-9][0-9]*)|' .
            '(?:grade/report/(?:grader|user)/index\.php\?id=[1-9][0-9]*)|' .
            '(?:calendar/view\.php\?view=upcoming))$~D';
        return array_values(array_filter($links, static fn($link) =>
            is_array($link) && is_string($link['url'] ?? null) &&
            is_string($link['label'] ?? null) && is_string($link['detail'] ?? null) &&
            preg_match($pattern, $link['url']) === 1));
    }

    private static function result(string $answer, array $links): array {
        return ['answer' => $answer, 'sources' => [], 'navigation_links' => $links,
            'insufficient_context' => false];
    }
}
