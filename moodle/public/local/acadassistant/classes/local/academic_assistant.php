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
    public function ask(string $question, array $conversationcontext = [], int $offset = 0, array $seen = []): array {
        $client = rag_client::from_current_user($this->transport);
        $context = (new academic_context_provider())->collect_for_question($question, $conversationcontext, $offset, $seen);
        $response = $client->query(
            $question,
            $context['course_ids'],
            $context['academic_context'],
            $conversationcontext
        );
        $response['continuation'] = $context['academic_context']['query']['has_more']
            ? ['question' => $context['context_question'], 'seen' => $context['continuation_seen']] : null;
        $response['context_question'] = $context['context_question'];
        $response['academic_provenance'] = [];
        if (in_array('calendar', $context['requested_categories'], true)) {
            $response['academic_provenance'][] = 'calendar';
        }
        if (array_intersect(
            ['courses', 'assignments', 'grades', 'teachers'],
            $context['requested_categories']
        )) {
            $response['academic_provenance'][] = 'academic';
        }
        return $response;
    }
}
