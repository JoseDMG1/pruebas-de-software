<?php
// This file is part of Moodle - http://moodle.org/
// Licensed under the GNU General Public License version 3 or later.
namespace local_acadassistant\local;
defined('MOODLE_INTERNAL') || die();

/** Display transcript text as accessible, escaped paragraphs and lists. */
final class answer_presenter {
    /** Build presentation HTML with Moodle's escaping helpers; never trust model markup. */
    public static function render(string $answer): string {
        $chunks = preg_split('/\n\s*\n/u', trim(str_replace(["\r\n", "\r"], "\n", $answer))) ?: [];
        $output = [];
        foreach ($chunks as $chunk) {
            $lines = explode("\n", trim($chunk));
            if (!$lines || $lines === ['']) {
                continue;
            }
            if (self::is_heading(trim($lines[0]))) {
                $output[] = \html_writer::tag('h3', s(trim($lines[0])), [
                    'class' => 'local-acadassistant-answer-heading',
                ]);
                array_shift($lines);
            }

            $items = [];
            $paragraphs = [];
            $currentitem = null;
            $flushitem = static function() use (&$currentitem, &$items): void {
                if ($currentitem !== null) {
                    $items[] = \html_writer::tag('li', $currentitem, [
                        'class' => 'local-acadassistant-answer-item',
                    ]);
                    $currentitem = null;
                }
            };
            foreach ($lines as $line) {
                if (preg_match('/^•\s+(.+)$/u', $line, $match)) {
                    $flushitem();
                    $currentitem = \html_writer::tag('span', s($match[1]), [
                        'class' => 'local-acadassistant-answer-item__title',
                    ]);
                } else if ($currentitem !== null && preg_match('/^\s{2,}(.+)$/u', $line, $match)) {
                    $currentitem .= \html_writer::tag('span', s($match[1]), [
                        'class' => 'local-acadassistant-answer-item__detail',
                    ]);
                } else {
                    $flushitem();
                    if (trim($line) !== '') {
                        $paragraphs[] = trim($line);
                    }
                }
            }
            $flushitem();
            if ($items) {
                $output[] = \html_writer::tag('ul', implode('', $items), [
                    'class' => 'local-acadassistant-answer-list',
                ]);
            }
            foreach ($paragraphs as $paragraph) {
                $class = preg_match('/^Según (?:Moodle|los datos visibles de Moodle)\b/u', $paragraph)
                    ? 'local-acadassistant-answer-note local-acadassistant-answer-note--source'
                    : 'local-acadassistant-answer-note';
                $output[] = \html_writer::tag('p', s($paragraph), ['class' => $class]);
            }
        }
        return implode("\n", $output);
    }

    private static function is_heading(string $line): bool {
        return preg_match(
            '/^(?:Información institucional:|Plan de estudio|'
            . 'Tareas (?:pendientes de entrega|entregadas|visibles)|'
            . 'Cursos (?:con matrícula vigente|que puedes consultar|que enseñas)|'
            . 'Docentes por curso|Calificaciones visibles|Calendario Moodle|'
            . 'Vencidas|Próximas, incluidas entregas futuras|Sin fecha)'
            . '(?:\s+\(\d+\))?:?$/u',
            $line
        ) === 1;
    }
}
