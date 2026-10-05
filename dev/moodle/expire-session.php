<?php
// Exercise Moodle's real timeout check on the next browser request, for a local fixture account.
define('CLI_SCRIPT', true);
require('/var/www/moodle/config.php');
$username = $argv[1] ?? '';
if ($CFG->wwwroot !== 'http://127.0.0.1:8088' ||
        !in_array($username, ['estudiante1', 'estudiante2', 'docente1', 'autoridad1'], true)) {
    throw new RuntimeException('Choose a local fixture account.');
}
$user = $DB->get_record('user', ['username' => $username], '*', MUST_EXIST);
$DB->set_field('sessions', 'timemodified', time() - $CFG->sessiontimeout - 60, ['userid' => $user->id]);
echo 'The next request from this account will exercise the Moodle timeout.' . PHP_EOL;
