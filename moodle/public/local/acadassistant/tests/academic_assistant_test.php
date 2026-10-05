<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

namespace local_acadassistant;

defined('MOODLE_INTERNAL') || die();

/** Tests the server-side assistant service at the Moodle-to-RAG seam. */
final class academic_assistant_test extends \advanced_testcase {
    public function test_empty_live_category_still_shows_its_moodle_provenance(): void {
        global $CFG;

        $this->resetAfterTest();
        $student = $this->getDataGenerator()->create_user();
        $this->setUser($student);
        $originalurl = $CFG->local_acadassistant_rag_url ?? null;
        $originalsecret = $CFG->local_acadassistant_rag_shared_secret ?? null;
        $CFG->local_acadassistant_rag_url = 'https://rag.example.test';
        $CFG->local_acadassistant_rag_shared_secret = 'a-test-secret-long-enough-for-hmac-sha256';
        $transport = static fn(): array => [
            'status' => 200,
            'body' => json_encode([
                'answer' => 'No hay tareas visibles.',
                'sources' => [],
                'insufficient_context' => false,
                'request_id' => 'test-request',
            ], JSON_THROW_ON_ERROR),
        ];
        try {
            $response = (new \local_acadassistant\local\academic_assistant($transport))
                ->ask('¿Qué tareas tengo pendientes?');
            $this->assertSame(['academic'], $response['academic_provenance']);
        } finally {
            if ($originalurl === null) {
                unset($CFG->local_acadassistant_rag_url);
            } else {
                $CFG->local_acadassistant_rag_url = $originalurl;
            }
            if ($originalsecret === null) {
                unset($CFG->local_acadassistant_rag_shared_secret);
            } else {
                $CFG->local_acadassistant_rag_shared_secret = $originalsecret;
            }
        }
    }

    public function test_global_question_sends_authorized_context_and_recent_turns_server_side(): void {
        global $CFG;

        $this->resetAfterTest();
        $firstcourse = $this->getDataGenerator()->create_course(['fullname' => 'Álgebra 101']);
        $secondcourse = $this->getDataGenerator()->create_course(['fullname' => 'Geometría 202']);
        $student = $this->getDataGenerator()->create_user();
        $this->getDataGenerator()->enrol_user($student->id, $firstcourse->id, 'student');
        $this->getDataGenerator()->enrol_user($student->id, $secondcourse->id, 'student');
        $assigngenerator = $this->getDataGenerator()->get_plugin_generator('mod_assign');
        foreach ([$firstcourse, $secondcourse] as $course) {
            $assigngenerator->create_instance([
                'course' => $course->id,
                'name' => 'Tarea semanal',
                'duedate' => time() + DAYSECS,
            ]);
        }
        $this->setUser($student);

        $originalurl = $CFG->local_acadassistant_rag_url ?? null;
        $originalsecret = $CFG->local_acadassistant_rag_shared_secret ?? null;
        $CFG->local_acadassistant_rag_url = 'https://rag.example.test';
        $CFG->local_acadassistant_rag_shared_secret = 'a-test-secret-long-enough-for-hmac-sha256';
        $requests = [];
        $transport = static function (string $url, string $body, array $headers) use (&$requests): array {
            $requests[] = [$url, $body, $headers];
            return [
                'status' => 200,
                'body' => json_encode([
                    'answer' => 'Hay una tarea en cada curso (según Moodle).',
                    'sources' => [],
                    'insufficient_context' => false,
                    'request_id' => 'test-request',
                ], JSON_THROW_ON_ERROR),
            ];
        };

        try {
            $history = [[
                'question' => '¿Qué tareas tengo en Álgebra 101?',
                'answer' => 'Tienes una tarea pendiente.',
            ]];
            $response = (new \local_acadassistant\local\academic_assistant($transport))
                ->ask('¿Y en Geometría?', $history);

            $this->assertSame(['academic'], $response['academic_provenance']);
            $this->assertCount(1, $requests);
            [$url, $body, $headers] = $requests[0];
            $payload = json_decode($body, true, flags: JSON_THROW_ON_ERROR);
            $this->assertSame('https://rag.example.test/api/v1/chat/query', $url);
            $courseids = $this->verified_course_ids($headers, $body);
            $this->assertSame([$firstcourse->id, $secondcourse->id], $courseids);
            $this->assertCount(2, $payload['academic_context']['assignments']);
            $this->assertSame($history, $payload['conversation_context']);
            $this->assertStringStartsWith('Bearer ', $headers['Authorization']);
            $this->assertArrayNotHasKey('Authorization', $response);
        } finally {
            if ($originalurl === null) {
                unset($CFG->local_acadassistant_rag_url);
            } else {
                $CFG->local_acadassistant_rag_url = $originalurl;
            }
            if ($originalsecret === null) {
                unset($CFG->local_acadassistant_rag_shared_secret);
            } else {
                $CFG->local_acadassistant_rag_shared_secret = $originalsecret;
            }
        }
    }

    /** Extract and sort the trusted scope from the signed request for assertions. */
    private function verified_course_ids(array $headers, string $body): array {
        $assertion = substr($headers['Authorization'], 7);
        [, $encodedclaims] = explode('.', $assertion);
        $padding = str_repeat('=', (4 - strlen($encodedclaims) % 4) % 4);
        $claims = json_decode(
            base64_decode(strtr($encodedclaims . $padding, '-_', '+/')),
            true,
            flags: JSON_THROW_ON_ERROR
        );
        $this->assertSame(hash('sha256', $body), $claims['body_sha256']);
        $courseids = $claims['courses'];
        sort($courseids, SORT_NUMERIC);
        return $courseids;
    }
}
