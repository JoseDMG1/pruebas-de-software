<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

namespace local_acadassistant\local;

defined('MOODLE_INTERNAL') || die();

use Closure;

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

    public static function interpret(string $question, array $history = []): array {
        $text = self::normalise($question);
        $followup = (new conversation_store())->is_follow_up($question);
        $previous = $history ? self::interpret($history[count($history) - 1]['question']) : null;
        $categories = [];
        $documentary = (bool)preg_match('/reglamento|normativa|nota minima|aprobatori|documento|silabo|codigo|tutoria/', $text);
        if (preg_match('/\b(cursos?|materias?|asignaturas?|llevo|matriculad[oa]s?|inscrit[oa]s?|enseno|imparto)\b/', $text) && (!$documentary || preg_match('/mis cursos|cursos tengo|materias llevo|estoy matriculad/', $text))) {
            $categories[] = 'courses';
        }
        if (preg_match('/\b(profesores?|profesoras?|docentes?|quien (?:me )?ensena|quien (?:me )?dicta|profes)\b/', $text)) {
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
        if (preg_match('/\b(calendario|eventos?|fechas?|cuando|inicia|empieza|comienza|ciclo|examen(?:es)?)\b/', $text) && !in_array('assignments', $categories)) {
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
        if (preg_match('/(?:ya |si )?(?:entregue|presente)|\bentregadas\b|\bpresentadas\b/', $text)) {
            $filter = 'submitted';
        } else if ($followup && $previous && !preg_match('/pendientes|todas?|todos?/', $text)) {
            $filter = $previous['assignment_filter'];
        }
        if (preg_match('/no (?:entregadas|presentadas)/', $text)) {
            $filter = 'pending';
        }
        $finance = (bool)preg_match('/cuotas?|pagos?|pagar|saldo|costando|cuanto.*(?:debo|cuesta)|precio.*matricula/', $text);
        // Only non-academic clauses go to documentary generation in a mixed query.
        $clauses = preg_split('/\s+y\s+|[;\n]/', $question);
        $documentclauses = [];
        foreach ($clauses as $clause) {
            $normal = self::normalise($clause);
            if (preg_match('/reglamento|normativa|aprobatori|documento|silabo|codigo|tutoria|biblioteca|ciclo/', $normal)) {
                $documentclauses[] = $clause;
            }
        }
        return [
            'categories' => array_values(array_unique($categories)),
            'course_mode' => $mode,
            'assignment_filter' => $filter,
            'finance' => $finance,
            'follow_up' => $followup,
            'ambiguous_task' => (bool)preg_match('/\b(cuando vence|cuando debo entregarla|esa tarea|esa entrega)\b/', $text),
            'document_question' => $documentclauses ? implode(' y ', $documentclauses) : ($categories || $finance ? '' : $question),
        ];
    }
}
