<?php
// Create a dedicated local account with a list longer than one assistant page.
define('CLI_SCRIPT', true);
require('/var/www/moodle/config.php');
require_once($CFG->libdir . '/testing/generator/lib.php');
if ($CFG->wwwroot !== 'http://127.0.0.1:8088' || !getenv('MOODLE_DEMO_PASSWORD')) {
    throw new RuntimeException('Restricted to the local test site.');
}
\core\session\manager::set_user(get_admin());
if (in_array('--cleanup', $argv, true)) {
    require_once($CFG->dirroot . '/course/lib.php');
    $fixtureuser = $DB->get_record('user', ['username' => 'estudiante_lista']);
    for ($i = 1; $i <= 22; $i++) {
        $course = $DB->get_record('course', [
            'shortname' => sprintf('LISTA%02d', $i), 'fullname' => sprintf('Z Lista %02d', $i),
        ]);
        if (!$course) {
            continue;
        }
        $enrolled = get_enrolled_users(context_course::instance($course->id), '', 0, 'u.id');
        foreach ($enrolled as $person) {
            if (!$fixtureuser || $person->id != $fixtureuser->id) {
                throw new RuntimeException('Unexpected enrolment in pagination fixture; cleanup stopped.');
            }
        }
        delete_course($course, false);
    }
    if ($fixtureuser) {
        $DB->set_field('user', 'suspended', 1, ['id' => $fixtureuser->id]);
    }
    echo "Pagination fixtures removed.\n";
    exit;
}
$generator = new testing_data_generator();
$user = $DB->get_record('user', ['username' => 'estudiante_lista']) ?: $generator->create_user([
    'username' => 'estudiante_lista', 'firstname' => 'Lista', 'lastname' => 'Prueba',
    'email' => 'lista@example.test', 'password' => getenv('MOODLE_DEMO_PASSWORD'), 'lang' => 'en',
]);
$DB->set_field('user', 'suspended', 0, ['id' => $user->id]);
for ($i = 1; $i <= 22; $i++) {
    $shortname = sprintf('LISTA%02d', $i);
    $course = $DB->get_record('course', ['shortname' => $shortname]) ?: $generator->create_course([
        'shortname' => $shortname, 'fullname' => sprintf('Z Lista %02d', $i), 'visible' => 1,
    ]);
    $generator->enrol_user($user->id, $course->id, 'student');
}
echo "Local pagination fixtures ready.\n";
