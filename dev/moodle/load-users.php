<?php
// Dedicated local load identities; does not modify the original demo accounts.
define('CLI_SCRIPT', true);
require('/var/www/moodle/config.php');
require_once($CFG->libdir . '/testing/generator/lib.php');
if ($CFG->wwwroot !== 'http://127.0.0.1:8088' || !getenv('MOODLE_DEMO_PASSWORD')) {
    throw new RuntimeException('Restricted to configured local test site.');
}
\core\session\manager::set_user(get_admin());
$generator = new testing_data_generator();
$studentrole = $DB->get_record('role', ['shortname' => 'student'], '*', MUST_EXIST);
$profiles = [];
for ($i = 1; $i <= 100; $i++) {
    $username = sprintf('carga%03d', $i);
    $source = $DB->get_record('user', ['username' => 'estudiante' . (($i - 1) % 2 + 1)], '*', MUST_EXIST);
    $user = $DB->get_record('user', ['username' => $username]) ?: $generator->create_user([
        'username' => $username, 'firstname' => 'Evaluación', 'lastname' => sprintf('Carga %03d', $i),
        'email' => $username . '@example.invalid', 'password' => getenv('MOODLE_DEMO_PASSWORD'),
        'lang' => 'en', 'timezone' => 'America/Lima',
    ]);
    $courses = enrol_get_users_courses($source->id, true, 'id, fullname, shortname, visible');
    $expected = [];
    foreach ($courses as $course) {
        if (!$course->visible) { continue; }
        $generator->enrol_user($user->id, $course->id, $studentrole->id);
        $expected[] = $course->fullname;
    }
    $profiles[] = ['username' => $username, 'user_id' => (int)$user->id, 'expected_courses' => $expected,
        'source_profile' => $source->username];
}
$allcourses = [];
foreach ($profiles as $profile) { $allcourses = array_unique(array_merge($allcourses, $profile['expected_courses'])); }
foreach ($profiles as &$profile) { $profile['forbidden_courses'] = array_values(array_diff($allcourses, $profile['expected_courses'])); }
unset($profile);
echo json_encode(['profiles' => $profiles, 'count' => count($profiles),
    'scope' => '100 distinct local student identities; enrolments mirror two prepared profiles, no copied grades or submissions.'], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE) . "\n";
