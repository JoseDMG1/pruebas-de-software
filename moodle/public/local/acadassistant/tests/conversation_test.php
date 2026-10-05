<?php
namespace local_acadassistant;
defined('MOODLE_INTERNAL') || die();

/** Public signed conversation contract tests. */
final class conversation_test extends \advanced_testcase {
    public function test_interpreter_request_uses_server_clock_and_rejects_unpermitted_plan(): void {
        global $CFG;
        $this->resetAfterTest();
        $student = $this->getDataGenerator()->create_user(['timezone' => 'America/Lima']);
        $this->setUser($student);
        $CFG->local_acadassistant_rag_url = 'https://rag.example.test';
        $CFG->local_acadassistant_rag_shared_secret = str_repeat('a', 40);
        $calls = 0;
        $transport = function($url, $body, $headers) use (&$calls): array {
            $calls++;
            $this->assertStringEndsWith('/api/v1/chat/interpret', $url);
            $request = json_decode($body, true);
            $this->assertSame('America/Lima', $request['runtime']['timezone']);
            $this->assertLessThanOrEqual(2, abs(time() - $request['runtime']['now']));
            $this->assertStringStartsWith('Bearer ', $headers['Authorization']);
            return ['status' => 200, 'body' => json_encode(['intent' => 'academic', 'categories' => ['sql']])];
        };
        $client = \local_acadassistant\local\rag_client::from_current_user($transport);
        try {
            $client->interpret('hola como estás');
            $this->fail('An unpermitted operation must never reach a Moodle reader.');
        } catch (\moodle_exception $e) {
            $this->assertSame('ragrequestfailed', $e->errorcode);
        }
        $this->assertSame(1, $calls);
    }
}
