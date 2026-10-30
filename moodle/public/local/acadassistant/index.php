<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

require_once(__DIR__ . '/../../config.php');

$context = context_system::instance();
$pageurl = new moodle_url('/local/acadassistant/index.php');
$PAGE->set_url($pageurl);
$PAGE->set_context($context);
require_login();
if (isguestuser()) {
    throw new moodle_exception('guestnotallowed', 'local_acadassistant');
}

$PAGE->set_cacheable(false);
$PAGE->set_pagelayout('standard');
$PAGE->set_title(get_string('assistant', 'local_acadassistant'));
$PAGE->set_heading(get_string('assistant', 'local_acadassistant'));

$store = new \local_acadassistant\local\conversation_store();
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    require_sesskey();
    $action = optional_param('action', '', PARAM_ALPHA);
    if ($action === 'new') {
        $store->clear();
    } else if ($action === 'ask') {
        $question = trim(optional_param('question', '', PARAM_TEXT));
        if ($question === '') {
            $store->set_error(get_string('questionrequired', 'local_acadassistant'));
        } else if (core_text::strlen($question) > 1000) {
            $store->set_error(get_string('questiontoolong', 'local_acadassistant'));
        } else {
            try {
                $cursor = $store->continuation();
                $continuing = \local_acadassistant\local\academic_question::is_continuation($question);
                if ($continuing && !$cursor) {
                    $response = ['answer' => 'No hay una lista pendiente de continuar. ¿Qué necesitas consultar?'];
                } else {
                    $response = (new \local_acadassistant\local\academic_assistant())
                        ->ask($continuing ? $cursor['question'] : $question,
                            $continuing ? [] : $store->context(),
                            0, $continuing ? $cursor['seen'] : [], $store->semantic_state());
                }
                $answer = $response['answer'] ?? null;
                if (!is_string($answer) || trim($answer) === '') {
                    throw new moodle_exception('ragrequestfailed', 'local_acadassistant');
                }
                $store->append(
                    $question,
                    $answer,
                    $response['sources'] ?? [],
                    $response['academic_provenance'] ?? [],
                    !($response['follow_up'] ?? false),
                    $response['continuation'] ?? null,
                    $response['context_question'] ?? null,
                    $response['semantic_state'] ?? null,
                    $response['navigation_links'] ?? []
                );
            } catch (\Throwable) {
                $store->set_error(get_string('assistantunavailable', 'local_acadassistant'));
            }
        }
    } else {
        $store->set_error(get_string('invalidaction', 'local_acadassistant'));
    }
    redirect($pageurl);
}

$messages = $store->messages();
foreach ($messages as &$message) {
    $message['answer_html'] = \local_acadassistant\local\answer_presenter::render($message['answer']);
    foreach ($message['sources'] as &$source) {
        $source['label'] = $source['scope'] === 'institutional'
            ? get_string('institutionalsource', 'local_acadassistant')
            : get_string('coursesource', 'local_acadassistant');
        $source['pagerange'] = $source['page_start'] . '-' . $source['page_end'];
        $source['pagelabel'] = get_string('pages', 'local_acadassistant', $source['pagerange']);
    }
    unset($source);
    $message['academiclabels'] = [];
    foreach ($message['academic_sources'] ?? [] as $provenance) {
        $message['academiclabels'][] = [
            'label' => get_string($provenance . 'provenance', 'local_acadassistant'),
        ];
    }
}
unset($message);

echo $OUTPUT->header();
echo $OUTPUT->render_from_template('local_acadassistant/chat', [
    'pageurl' => $pageurl->out(false),
    'sesskey' => sesskey(),
    'messages' => $messages,
    'hasmessages' => !empty($messages),
    'error' => $store->take_error(),
]);
echo $OUTPUT->footer();
