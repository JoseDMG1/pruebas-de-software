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

/** Server-side client for authenticated requests to the RAG service. */
final class rag_client {
    private const ASSERTION_TTL = 60;
    private const MAX_CONTEXT_BYTES = 32768;
    private const ACADEMIC_CONTEXT_CATEGORIES = ['courses', 'assignments', 'grades'];

    /**
     * @param callable|null $transport Test seam. Receives URL, body, and headers; returns status/body.
     */
    private function __construct(
        private readonly string $baseurl,
        private readonly string $secret,
        private readonly int $userid,
        private readonly ?Closure $transport = null,
    ) {
    }

    /**
     * Build a client for the authenticated non-guest Moodle user.
     *
     * @param callable|null $transport Optional transport used by the contract test.
     * @return self
     */
    public static function from_current_user(?callable $transport = null): self {
        global $CFG, $USER;

        if (!isloggedin() || isguestuser() || empty($USER->id)) {
            throw new \moodle_exception('requirelogin', 'error');
        }

        $baseurl = trim((string)($CFG->local_acadassistant_rag_url ?? ''));
        $secret = (string)($CFG->local_acadassistant_rag_shared_secret ?? '');
        if ($baseurl === '' || strlen($secret) < 32) {
            throw new \moodle_exception('ragnotconfigured', 'local_acadassistant');
        }

        self::validate_baseurl($baseurl);
        return new self($baseurl, $secret, (int)$USER->id, $transport ? Closure::fromCallable($transport) : null);
    }

    /**
     * Send a query with a short-lived signed identity and authorized course scope.
     *
     * Course IDs and academic context must already have been obtained by trusted Moodle code after
     * checking the current user's capabilities; they must never come directly from browser input.
     *
     * @param string $query User question.
     * @param int[] $authorizedcourseids Course IDs Moodle has authorized for the current user.
     * @param array $academiccontext Authorized courses, assignments, or grades from Moodle.
     * @return array Decoded RAG response.
     */
    public function query(string $query, array $authorizedcourseids = [], array $academiccontext = []): array {
        $query = trim($query);
        if ($query === '' || strlen($query) > 1000) {
            throw new \moodle_exception('ragrequestfailed', 'local_acadassistant');
        }

        $courseids = [];
        foreach ($authorizedcourseids as $courseid) {
            if (!is_int($courseid) || $courseid < 1) {
                throw new \moodle_exception('ragrequestfailed', 'local_acadassistant');
            }
            $courseids[$courseid] = $courseid;
        }
        $courseids = array_values($courseids);
        sort($courseids, SORT_NUMERIC);
        $this->validate_current_user_and_course_scope($courseids);
        if (array_diff(array_keys($academiccontext), self::ACADEMIC_CONTEXT_CATEGORIES)) {
            throw new \moodle_exception('ragrequestfailed', 'local_acadassistant');
        }

        try {
            $body = json_encode(
                ['query' => $query, 'academic_context' => (object)$academiccontext],
                JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE
            );
        } catch (\JsonException) {
            throw new \moodle_exception('ragrequestfailed', 'local_acadassistant');
        }
        if (strlen($body) > self::MAX_CONTEXT_BYTES) {
            throw new \moodle_exception('ragrequestfailed', 'local_acadassistant');
        }

        $now = time();
        $claims = [
            'iss' => 'moodle',
            'aud' => 'rag-service',
            'sub' => (string)$this->userid,
            'courses' => $courseids,
            'iat' => $now,
            'exp' => $now + self::ASSERTION_TTL,
            'jti' => bin2hex(random_bytes(16)),
            'body_sha256' => hash('sha256', $body),
        ];
        $assertion = $this->sign_assertion($claims);
        $url = rtrim($this->baseurl, '/') . '/api/v1/chat/query';
        $headers = [
            'Content-Type' => 'application/json',
            'Authorization' => 'Bearer ' . $assertion,
        ];

        if ($this->transport !== null) {
            $response = ($this->transport)($url, $body, $headers);
        } else {
            $response = $this->post($url, $body, $assertion);
        }

        if (!is_array($response) || ($response['status'] ?? 0) < 200 || ($response['status'] ?? 0) >= 300) {
            throw new \moodle_exception('ragrequestfailed', 'local_acadassistant');
        }
        try {
            $decoded = json_decode((string)($response['body'] ?? ''), true, flags: JSON_THROW_ON_ERROR);
        } catch (\JsonException) {
            throw new \moodle_exception('ragrequestfailed', 'local_acadassistant');
        }
        if (!is_array($decoded)) {
            throw new \moodle_exception('ragrequestfailed', 'local_acadassistant');
        }
        return $decoded;
    }

    /** Confirm the session is unchanged and every course is accessible in Moodle. */
    private function validate_current_user_and_course_scope(array $courseids): void {
        global $USER;

        if (!isloggedin() || isguestuser() || empty($USER->id) || (int)$USER->id !== $this->userid) {
            throw new \moodle_exception('requirelogin', 'error');
        }
        foreach ($courseids as $courseid) {
            try {
                $course = get_course($courseid);
            } catch (\moodle_exception) {
                throw new \moodle_exception('ragrequestfailed', 'local_acadassistant');
            }
            if (!$course || !can_access_course($course, $USER, '', true)) {
                throw new \moodle_exception('ragrequestfailed', 'local_acadassistant');
            }
        }
    }

    /** Validate service URL scheme before sending a server-side request. */
    private static function validate_baseurl(string $baseurl): void {
        $parts = parse_url($baseurl);
        if (!is_array($parts) || empty($parts['host']) || isset($parts['user']) || isset($parts['pass'])
                || isset($parts['query']) || isset($parts['fragment'])) {
            throw new \moodle_exception('ragnotconfigured', 'local_acadassistant');
        }

        $scheme = strtolower($parts['scheme'] ?? '');
        $host = strtolower(trim($parts['host'], '[]'));
        $loopback = in_array($host, ['localhost', '127.0.0.1', '::1'], true);
        if ($scheme !== 'https' && !($scheme === 'http' && $loopback)) {
            throw new \moodle_exception('ragnotconfigured', 'local_acadassistant');
        }
    }

    /** Create a compact HS256 JWT assertion. */
    private function sign_assertion(array $claims): string {
        $header = ['alg' => 'HS256', 'typ' => 'JWT'];
        $encodedheader = self::base64url_encode(json_encode($header, JSON_THROW_ON_ERROR));
        $encodedclaims = self::base64url_encode(json_encode($claims, JSON_THROW_ON_ERROR));
        $signinginput = $encodedheader . '.' . $encodedclaims;
        $signature = hash_hmac('sha256', $signinginput, $this->secret, true);
        return $signinginput . '.' . self::base64url_encode($signature);
    }

    /** Encode data as an unpadded base64url segment. */
    private static function base64url_encode(string $value): string {
        return rtrim(strtr(base64_encode($value), '+/', '-_'), '=');
    }

    /** Send the request using Moodle's server-side cURL wrapper. */
    private function post(string $url, string $body, string $assertion): array {
        $curl = new \curl();
        $responsebody = $curl->post($url, $body, [
            'CURLOPT_HTTPHEADER' => [
                'Content-Type: application/json',
                'Authorization: Bearer ' . $assertion,
            ],
            'CURLOPT_TIMEOUT' => 30,
            // Never forward the bearer assertion to a redirect target.
            'CURLOPT_FOLLOWLOCATION' => false,
        ]);
        if ($curl->get_errno() !== 0) {
            throw new \moodle_exception('ragrequestfailed', 'local_acadassistant');
        }
        $info = $curl->get_info();
        return ['status' => (int)($info['http_code'] ?? 0), 'body' => $responsebody];
    }
}
