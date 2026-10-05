<?php
declare(strict_types=1);

define('MOODLE_INTERNAL', true);
$GLOBALS['testloggedin'] = true;
$GLOBALS['testguest'] = false;
$GLOBALS['USER'] = (object)['id' => 42];
$GLOBALS['CFG'] = (object)[
    'local_acadassistant_rag_url' => 'https://rag.example.test/',
    'local_acadassistant_rag_shared_secret' => 'a-test-secret-long-enough-for-hmac-sha256',
];
$GLOBALS['testallowedcourses'] = [10, 20];

function isloggedin(): bool {
    return $GLOBALS['testloggedin'];
}

function isguestuser(): bool {
    return $GLOBALS['testguest'];
}

function get_course(int $courseid): object {
    return (object)['id' => $courseid];
}

function can_access_course(object $course, object $user, string $capability = '', bool $onlyactive = false): bool {
    return in_array($course->id, $GLOBALS['testallowedcourses'], true);
}

class moodle_exception extends RuntimeException {
    public function __construct(string $errorcode, string $module = 'error') {
        parent::__construct($module . ':' . $errorcode);
    }
}

require_once __DIR__ . '/../classes/local/rag_client.php';

function check(bool $condition, string $message): void {
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

function decode_segment(string $segment): string {
    return base64_decode(strtr($segment . str_repeat('=', (4 - strlen($segment) % 4) % 4), '-_', '+/'));
}

$requests = [];
$transport = static function (string $url, string $body, array $headers) use (&$requests): array {
    $requests[] = [$url, $body, $headers];
    return ['status' => 200, 'body' => '{"answer":"ok"}'];
};
$client = \local_acadassistant\local\rag_client::from_current_user($transport);
$academiccontext = [
    'assignments' => [['name' => 'Informe', 'status' => 'submitted', 'source' => 'Moodle']],
    'calendar' => [['name' => 'Inicio de ciclo', 'source' => 'Calendario Moodle']],
];
$conversationcontext = [
    ['question' => '¿Cuándo inicia el segundo ciclo?', 'answer' => 'En agosto.'],
];
$result = $client->query(
    '¿Qué fecha exacta?', [10, 20], $academiccontext, $conversationcontext
);

check($result === ['answer' => 'ok'], 'The Moodle client should decode the RAG response.');
check(count($requests) === 1, 'The Moodle client should send one server-side request.');
[$url, $body, $headers] = $requests[0];
check($url === 'https://rag.example.test/api/v1/chat/query', 'The RAG query URL is incorrect.');
check(!str_contains($body, $GLOBALS['CFG']->local_acadassistant_rag_shared_secret), 'The secret must not be sent in the JSON body.');
check($headers['Content-Type'] === 'application/json', 'The request must be JSON.');
$authorization = $headers['Authorization'] ?? '';
check(str_starts_with($authorization, 'Bearer '), 'The request must carry a signed bearer assertion.');
// The client returns only the RAG result to its caller; neither service credential nor assertion
// belongs in a response that a Moodle page could serialize to the browser.
$browserresponse = json_encode($result);
check(!str_contains($browserresponse, $GLOBALS['CFG']->local_acadassistant_rag_shared_secret), 'The response must not contain the service secret.');
check(!str_contains($browserresponse, $authorization), 'The response must not contain the service assertion.');
$parts = explode('.', substr($authorization, 7));
check(count($parts) === 3, 'The bearer assertion must be a three-part signed token.');
$claims = json_decode(decode_segment($parts[1]), true, flags: JSON_THROW_ON_ERROR);
$expectedsignature = rtrim(strtr(base64_encode(hash_hmac(
    'sha256', $parts[0] . '.' . $parts[1], $GLOBALS['CFG']->local_acadassistant_rag_shared_secret, true,
)), '+/', '-_'), '=');
check(hash_equals($expectedsignature, $parts[2]), 'The assertion signature must use the Moodle server secret.');
check($claims['sub'] === '42', 'The assertion identity must come from the authenticated Moodle user.');
check($claims['courses'] === [10, 20], 'The assertion must include the authorized course context.');
check($claims['iss'] === 'moodle' && $claims['aud'] === 'rag-service', 'The assertion audience is incorrect.');
check($claims['exp'] > $claims['iat'] && $claims['exp'] - $claims['iat'] <= 120, 'The assertion must have a short lifetime.');
check($claims['body_sha256'] === hash('sha256', $body), 'The assertion must bind the complete request body.');
$decodedbody = json_decode($body, true, flags: JSON_THROW_ON_ERROR);
check($decodedbody['academic_context'] === $academiccontext, 'The signed body must contain authorized academic context.');
check(
    $decodedbody['conversation_context'] === $conversationcontext,
    'The signed body must contain only the current conversation context.'
);

$GLOBALS['testguest'] = true;
$guestrejected = false;
try {
    \local_acadassistant\local\rag_client::from_current_user($transport);
} catch (moodle_exception) {
    $guestrejected = true;
}
check($guestrejected, 'Guest users must not obtain an authenticated RAG client.');
check(count($requests) === 1, 'A guest must not make a server-side RAG request.');

$GLOBALS['testguest'] = false;
$GLOBALS['testallowedcourses'] = [10];
$courserejected = false;
try {
    $client->query('Query an unauthorized course', [10, 20]);
} catch (moodle_exception) {
    $courserejected = true;
}
check($courserejected, 'The Moodle client must reject a course Moodle does not authorize.');
check(count($requests) === 1, 'An unauthorized course must not reach the RAG service.');

$contextrejected = false;
try {
    $client->query('Query with unrelated profile data', [], ['profile' => ['email' => 'private@example.test']]);
} catch (moodle_exception) {
    $contextrejected = true;
}
check($contextrejected, 'The Moodle client must reject unapproved academic context categories.');
check(count($requests) === 1, 'Unapproved academic context must not reach the RAG service.');

$historyrejected = false;
try {
    $client->query('Query with oversized history', [], [], array_fill(0, 5, [
        'question' => 'Previous question',
        'answer' => 'Previous answer',
    ]));
} catch (moodle_exception) {
    $historyrejected = true;
}
check($historyrejected, 'The Moodle client must bound conversation context.');
check(count($requests) === 1, 'Oversized conversation context must not reach the RAG service.');

$GLOBALS['testallowedcourses'] = [10, 20];
$GLOBALS['USER']->id = 99;
$userrejected = false;
try {
    $client->query('Query after Moodle user changed');
} catch (moodle_exception) {
    $userrejected = true;
}
check($userrejected, 'The Moodle client must reject a changed authenticated user.');
check(count($requests) === 1, 'A changed user must not reach the RAG service.');

echo "Moodle RAG client contract passed.\n";
