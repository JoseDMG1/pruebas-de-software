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

    /** Interpret before authorizing bounded, live native reads. */
    public function ask(string $question, array $conversationcontext = [], int $offset = 0,
            array $seen = [], array $semanticstate = []): array {
        $client = rag_client::from_current_user($this->transport);
        $plan = $client->interpret($question, $conversationcontext, $semanticstate);
        if (!$plan['availability'] && !$plan['availability_unknown'] && $plan['intent'] === 'weekly_plan') {
            $plan['availability'] = $semanticstate['availability'] ?? null;
            $plan['availability_unknown'] = $semanticstate['availability_unknown'] ?? false;
        }
        if ($plan['intent'] === 'weekly_plan' && $plan['follow_up'] && !$plan['week_explicit'] &&
                ($semanticstate['topic']['intent'] ?? '') === 'weekly_plan' && !$plan['week_start'] && !$plan['week_offset']) {
            $plan['week_start'] = $semanticstate['week_start'] ?? '';
            $plan['week_offset'] = $semanticstate['week_offset'] ?? 0;
        }
        $context = ['course_ids' => [], 'academic_context' => [], 'requested_categories' => [],
            'context_question' => $question, 'continuation_seen' => []];
        if (in_array($plan['intent'], ['academic', 'document', 'weekly_plan'], true)) {
            $provider = new academic_context_provider();
            $context = $provider->collect_for_plan($plan, $conversationcontext, $offset, $seen, $question);
            if ($plan['intent'] === 'weekly_plan') {
                // Native access is revalidated for every page; neither names nor cursors grant access.
                for ($page = 1; $page < 10 && $context['academic_context']['query']['has_more']; $page++) {
                    try {
                        $next = $provider->collect_for_plan($plan, $conversationcontext, 0, $context['continuation_seen'], $question);
                    } catch (\Throwable) {
                        $context['academic_context']['query']['complete'] = false;
                        $context['academic_context']['query']['notices'][] =
                            'No pude leer las páginas restantes de tareas. Acota a un curso o reintenta.';
                        break;
                    }
                    $merged = array_merge($context['academic_context']['assignments'] ?? [],
                        $next['academic_context']['assignments'] ?? []);
                    if (strlen(json_encode($merged)) > 18000 ||
                            $next['continuation_seen'] === $context['continuation_seen']) {
                        break;
                    }
                    $context['academic_context']['assignments'] = $merged;
                    $context['academic_context']['query']['has_more'] = $next['academic_context']['query']['has_more'];
                    $context['academic_context']['query']['complete'] = $context['academic_context']['query']['complete'] &&
                        $next['academic_context']['query']['complete'];
                    $context['course_ids'] = array_values(array_unique(array_merge($context['course_ids'], $next['course_ids'])));
                    $context['continuation_seen'] = $next['continuation_seen'];
                }
            }
        }
        $response = $client->query($question, $context['course_ids'], $context['academic_context'],
            $plan['follow_up'] ? $conversationcontext : [], $plan, rag_client::runtime());
        $response['continuation'] = ($context['academic_context']['query']['has_more'] ?? false) &&
            $plan['intent'] !== 'weekly_plan'
            ? ['question' => $context['context_question'], 'seen' => $context['continuation_seen']] : null;
        $response['context_question'] = $context['context_question'];
        $response['follow_up'] = $plan['follow_up'];
        $response['semantic_state'] = $semanticstate;
        if (in_array($plan['intent'], ['academic', 'document', 'weekly_plan'], true) ||
                ($plan['intent'] === 'clarify' && $plan['clarification'] === 'requests')) {
            $response['semantic_state']['topic'] = $plan;
            if (in_array($plan['intent'], ['academic', 'document', 'weekly_plan'], true)) {
                $response['semantic_state']['task_choices'] = $context['task_choices'] ?? [];
            }
            if ($plan['intent'] === 'academic') {
                $response['semantic_state']['topic']['scope_question'] = $context['context_question'];
            }
        }
        if ($plan['intent'] === 'weekly_plan' && ($plan['availability'] || $plan['availability_unknown'])) {
            $response['semantic_state']['availability'] = $plan['availability'];
            $response['semantic_state']['availability_unknown'] = $plan['availability_unknown'];
        }
        if ($plan['intent'] === 'weekly_plan') {
            $response['semantic_state']['week_offset'] = $plan['week_offset'];
            $response['semantic_state']['week_start'] = $plan['week_start'];
        }
        $response['academic_provenance'] = [];
        if (in_array('calendar', $context['requested_categories'], true)) {
            $response['academic_provenance'][] = 'calendar';
        }
        if (array_intersect(['courses', 'assignments', 'grades', 'teachers'], $context['requested_categories'])) {
            $response['academic_provenance'][] = 'academic';
        }
        return $response;
    }
}
