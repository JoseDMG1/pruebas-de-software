<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

namespace local_acadassistant\local;

defined('MOODLE_INTERNAL') || die();

/** Keeps a bounded assistant conversation in the current authenticated Moodle session. */
final class conversation_store {
    private const MAX_DISPLAY_TURNS = 8;
    private const MAX_CONTEXT_TURNS = 3;
    private const MAX_ANSWER_CHARS = 12000;
    private const MAX_EXCERPT_CHARS = 500;

    /** Return recent turns in the signed RAG context format. */
    public function context(): array {
        $state = $this->state();
        return $this->format_context($state['turns']);
    }

    /** Decide whether a question explicitly depends on the previous exchange. */
    public function is_follow_up(string $question): bool {
        if (academic_question::is_continuation($question)) {
            return true;
        }
        $turns = $this->state()['turns'];
        if ($turns && str_contains($turns[count($turns) - 1]['answer'], '¿De cuál tarea')) {
            return true;
        }
        $question = \core_text::strtolower(trim($question));
        $question = preg_replace('/^[\p{P}\s]+/u', '', $question);
        return (bool)preg_match(
            '/^(?:y\b|entonces\b|eso\b|esa\b|ese\b|también\b|además\b|en ese\b|en esa\b|de ese\b|de esa\b)|\b(?:fecha exacta|hora exacta|cuál de ellos|qué fecha exacta)\b/u',
            $question
        );
    }

    /** Return only recent turns in the current topic when the question is a follow-up. */
    public function context_for_question(string $question): array {
        if (!$this->is_follow_up($question)) {
            return [];
        }
        $turns = $this->state()['turns'];
        for ($index = count($turns) - 1; $index >= 0; $index--) {
            if (!empty($turns[$index]['contextbreak'])) {
                $turns = array_slice($turns, $index);
                break;
            }
        }
        return $this->format_context($turns);
    }

    /** Return the visible messages for this conversation. */
    public function messages(): array {
        return $this->state()['turns'];
    }

    /** Append a response and retain only the bounded active conversation. */
    public function append(
        string $question,
        string $answer,
        array $sources,
        array $academicprovenance = [],
        bool $contextbreak = false,
        ?array $continuation = null
    ): void {
        $state = $this->state();
        $safeSources = [];
        foreach (array_slice($sources, 0, 4) as $source) {
            if (!is_array($source)) {
                continue;
            }
            $safeSources[] = [
                'title' => (string)($source['title'] ?? ''),
                'filename' => (string)($source['filename'] ?? ''),
                'scope' => in_array($source['scope'] ?? '', ['institutional', 'course'], true)
                    ? $source['scope'] : '',
                'page_start' => max(0, (int)($source['page_start'] ?? 0)),
                'page_end' => max(0, (int)($source['page_end'] ?? 0)),
                'excerpt' => \core_text::substr((string)($source['excerpt'] ?? ''), 0, self::MAX_EXCERPT_CHARS),
            ];
        }
        $state['turns'][] = [
            'question' => \core_text::substr(trim($question), 0, 1000),
            'answer' => \core_text::substr(trim($answer), 0, self::MAX_ANSWER_CHARS),
            'sources' => $safeSources,
            'academic_sources' => array_values(array_intersect(
                ['calendar', 'academic'],
                $academicprovenance
            )),
            'contextbreak' => $contextbreak,
        ];
        $state['continuation'] = $continuation;
        $state['turns'] = array_slice($state['turns'], -self::MAX_DISPLAY_TURNS);
        $this->save($state);
    }

    /** The cursor is never exposed to the browser and belongs to this identity/session. */
    public function continuation(): ?array {
        return $this->state()['continuation'] ?? null;
    }

    /** Clear only the current user's conversation. */
    public function clear(): void {
        $this->save(['userid' => $this->current_user_id(), 'turns' => [], 'error' => null]);
    }

    /** Set one short-lived page notice in the current session. */
    public function set_error(string $message): void {
        $state = $this->state();
        $state['error'] = $message;
        $this->save($state);
    }

    /** Read and clear the current page notice. */
    public function take_error(): ?string {
        $state = $this->state();
        $message = $state['error'];
        $state['error'] = null;
        $this->save($state);
        return $message;
    }

    /** Reset state whenever the active Moodle identity differs from its owner. */
    private function state(): array {
        global $SESSION;

        $state = $SESSION->local_acadassistant_conversation ?? null;
        if (!is_array($state) || ($state['userid'] ?? null) !== $this->current_user_id() ||
                !is_array($state['turns'] ?? null)) {
            $state = ['userid' => $this->current_user_id(), 'turns' => [], 'error' => null];
            $this->save($state);
        }
        $state['error'] = is_string($state['error'] ?? null) ? $state['error'] : null;
        return $state;
    }

    private function save(array $state): void {
        global $SESSION;
        $SESSION->local_acadassistant_conversation = $state;
    }

    /** Reference numbers belong to one retrieval batch; keep them only in the visible transcript. */
    private function format_context(array $turns): array {
        return array_map(static fn(array $turn): array => [
            'question' => \core_text::substr($turn['question'], 0, 500),
            'answer' => trim(\core_text::substr(preg_replace('/\[\d+\]/', '', $turn['answer']), 0, 1200)),
        ], array_slice($turns, -self::MAX_CONTEXT_TURNS));
    }

    private function current_user_id(): int {
        global $USER;
        return (int)$USER->id;
    }
}
