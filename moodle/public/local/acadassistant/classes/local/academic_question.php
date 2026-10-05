<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

namespace local_acadassistant\local;

defined('MOODLE_INTERNAL') || die();

/** Interprets supported academic operations without granting access to any record. */
final class academic_question {
    public static function normalise(string $text): string {
        $ascii = iconv('UTF-8', 'ASCII//TRANSLIT//IGNORE', $text);
        return trim(preg_replace('/\s+/', ' ', \core_text::strtolower($ascii === false ? $text : $ascii)));
    }

    public static function is_continuation(string $question): bool {
        return (bool)preg_match('/^(?:continua|continuar|sigue|siguiente|ver mas|mas resultados|muestrame mas)[.!? ]*$/',
            self::normalise($question));
    }

    /** Decide from the supplied topic only; no hidden session dependency. */
    public static function is_follow_up(string $question, array $history = []): bool {
        $text = self::normalise($question);
        if (self::is_continuation($question)) {
            return true;
        }
        $text = preg_replace('/^[\p{P}\s]+/u', '', $text);
        if (preg_match('/^(?:y\b|entonces\b|me referia\b|queria decir\b|eso\b|esa\b|ese\b|tambien\b|ademas\b|en ese\b|en esa\b|de ese\b|de esa\b)|\b(?:fecha exacta|hora exacta|cual de ellos|esa tarea|esa entrega)\b/u', $text)) {
            return true;
        }
        $last = $history ? $history[count($history) - 1] : null;
        if ($last && str_contains($last['answer'], '¿De cuál tarea')) {
            return !preg_match('/^(?:que|quien|quienes|como|cuanto|cuando|cuales|cual)\b/u', $text);
        }
        return false;
    }

    public static function interpret(string $question, array $history = []): array {
        $clauses = preg_split('/\s+y\s+|[;\n]/u', $question);
        $academicclauses = [];
        $documentclauses = [];
        foreach ($clauses as $clause) {
            $normal = self::normalise($clause);
            $asksaboutcycle = str_contains($normal, 'ciclo') &&
                !preg_match('/profesor|docente|mis cursos|cursos tengo|materias llevo|matriculad|inscrit|tareas|entregas|calificaciones/', $normal);
            $isdocument = $asksaboutcycle ||
                (bool)preg_match('/reglamento|normativa|nota minima|aprobatori|documento|silabo|codigo|tutoria|biblioteca/', $normal);
            if ($isdocument) {
                $documentclauses[] = $clause;
            }
            if (!$isdocument || preg_match('/mis cursos|cursos tengo|materias llevo|mis tareas|tareas tengo|mis calificaciones|mis profesores|ciclo|calendario/', $normal)) {
                $academicclauses[] = $clause;
            }
        }
        $text = self::normalise(implode(' y ', $academicclauses));
        $followup = self::is_follow_up($question, $history);
        $previous = $history ? self::interpret($history[count($history) - 1]['question'], array_slice($history, 0, -1)) : null;
        $categories = [];
        $documentary = (bool)preg_match('/reglamento|normativa|nota minima|aprobatori|documento|silabo|codigo|tutoria/', $text);
        if (preg_match('/\b(cursos?|materias?|asignaturas?|llevo|matriculad[oa]s?|inscrit[oa]s?|enseno|imparto)\b/', $text) && (!$documentary || preg_match('/mis cursos|cursos tengo|materias llevo|estoy matriculad/', $text))) {
            $categories[] = 'courses';
        }
        if (preg_match('/\b(profesores?|profesoras?|docentes?|quienes? (?:me )?ensenan?|quienes? (?:me )?dictan?|profes)\b/', $text)) {
            $categories[] = 'teachers';
            if (!preg_match('/mis cursos|cursos tengo|materias llevo/', $text)) {
                $categories = array_values(array_diff($categories, ['courses']));
            }
        }
        if (preg_match('/\b(tareas?|actividades?|entregas?|entregad[oa]s?|entregar|presentar|subir|pendientes?|faltantes?|atrasad[oa]s?|vence|vencen|vencimiento|plazos?)\b/', $text)) {
            $categories[] = 'assignments';
        }
        if (preg_match('/\b(calificacion(?:es)?|calificadas?|notas?|promedios?|puntajes?)\b/', $text) && !$documentary) {
            $categories[] = 'grades';
        }
        if ((preg_match('/\b(calendario|eventos?|fechas?|cuando|inicia|empieza|comienza|examen(?:es)?)\b/', $text) ||
                (str_contains($text, 'ciclo') && !$categories)) && !in_array('assignments', $categories)) {
            $categories[] = 'calendar';
        }
        if ($followup && $previous) {
            if (!$categories || ($categories === ['calendar'] && in_array('assignments', $previous['categories']))) {
                $categories = $previous['categories'];
            }
        }
        $mode = preg_match('/consultar|disponibles|acceso|puedo ver/', $text) ? 'accessible' : 'enrolled';
        if (preg_match('/enseno|imparto|dicto|a mi cargo/', $text)) {
            $mode = 'teaching';
        } else if ($followup && $previous && !preg_match('/mis |tengo|llevo|matriculad|consultar|disponibles/', $text)) {
            $mode = $previous['course_mode'];
        }
        $filter = preg_match('/\b(todas?|todos?)\b/', $text) ? 'all' : 'pending';
        if (preg_match('/(?:ya |si )?(?:entregue|presente)|\bentregad[oa]s?\b|\bpresentad[oa]s?\b/', $text)) {
            $filter = 'submitted';
        } else if ($followup && $previous && !preg_match('/pendientes|todas?|todos?/', $text)) {
            $filter = $previous['assignment_filter'];
        }
        if (preg_match('/no (?:he )?(?:entregad[oa]s?|presentad[oa]s?|entregue|presente)/', $text)) {
            $filter = 'pending';
        }
        $finance = (bool)preg_match('/cuotas?|pagos?|pagar|saldo|costando|cuanto.*(?:debo|cuesta)|precio.*matricula/', $text);
        return [
            'categories' => array_values(array_unique($categories)),
            'course_mode' => $mode,
            'teacher_confirmation' => in_array('teachers', $categories, true) &&
                (bool)preg_match('/\b(unic[oa]s?|nadie mas|ningun[oa]? otr[oa]|solo (?:un|una|ese|esa|el|la))\b/', $text),
            'assignment_filter' => $filter,
            'finance' => $finance,
            'follow_up' => $followup,
            'ambiguous_task' => (bool)preg_match('/\b(cuando vence|cuando debo entregarla|esa tarea|esa entrega)\b/', $text),
            'scope_question' => $academicclauses && $categories ? implode(' y ', $academicclauses) : $question,
            'document_question' => $documentclauses ? implode(' y ', $documentclauses) : ($categories || $finance ? '' : $question),
        ];
    }
}
