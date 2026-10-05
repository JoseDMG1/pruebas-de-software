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
    public function ask(string $question): array {
        $client = rag_client::from_current_user($this->transport);
        $context = (new academic_context_provider())->collect_for_question($question);
        return $client->query($question, $context['course_ids'], $context['academic_context']);
    }
}
