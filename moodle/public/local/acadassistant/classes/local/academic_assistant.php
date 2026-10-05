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

/** Coordinates live academic context collection and the signed RAG request. */
final class academic_assistant {
    private readonly ?Closure $transport;

    /** @param callable|null $transport Optional server transport test seam. */
    public function __construct(?callable $transport = null) {
        $this->transport = $transport ? Closure::fromCallable($transport) : null;
    }

    /** Collect authorized Moodle data and send it with the current question. */
    public function ask(string $question, array $conversationcontext = []): array {
        $client = rag_client::from_current_user($this->transport);
        $recentquestions = array_column(array_slice($conversationcontext, -2), 'question');
        $contextquestion = implode(' ', array_merge($recentquestions, [$question]));
        $context = (new academic_context_provider())->collect_for_question($contextquestion);
        $response = $client->query(
            $question,
            $context['course_ids'],
            $context['academic_context'],
            $conversationcontext
        );
        $response['academic_provenance'] = [];
        if (in_array('calendar', $context['requested_categories'], true)) {
            $response['academic_provenance'][] = 'calendar';
        }
        if (array_intersect(
            ['courses', 'assignments', 'grades'],
            $context['requested_categories']
        )) {
            $response['academic_provenance'][] = 'academic';
        }
        return $response;
    }
}
