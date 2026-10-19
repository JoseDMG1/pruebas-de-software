<?php
// Local-only, repeatable fixtures for the Sprint 2 browser checks.
define('CLI_SCRIPT', true);
require('/var/www/moodle/config.php');
require_once($CFG->libdir . '/testing/generator/lib.php');
require_once($CFG->libdir . '/gradelib.php');
require_once($CFG->dirroot . '/calendar/lib.php');
require_once($CFG->dirroot . '/mod/assign/locallib.php');

if ($CFG->wwwroot !== 'http://127.0.0.1:8088' || !getenv('MOODLE_DEMO_PASSWORD')) {
    throw new RuntimeException('This fixture script is restricted to the local test site.');
}
\core\session\manager::set_user(get_admin());
$generator = new testing_data_generator();
$users = [];
foreach ([
    'estudiante1' => ['Ana', 'Prueba'],
    'estudiante2' => ['Luis', 'Prueba'],
    'docente1' => ['Carla', 'Docente'],
    'autoridad1' => ['Mario', 'Direccion'],
] as $username => [$firstname, $lastname]) {
    $users[$username] = $DB->get_record('user', ['username' => $username]) ?: $generator->create_user([
        'username' => $username,
        'firstname' => $firstname,
        'lastname' => $lastname,
        'email' => $username . '@example.test',
        'password' => getenv('MOODLE_DEMO_PASSWORD'),
        'lang' => 'en',
    ]);
}
$courses = [];
foreach (['ALG101' => 'Algebra 101', 'BIO102' => 'Biologia 102', 'RES103' => 'Reservado 103'] as $short => $name) {
    $courses[$short] = $DB->get_record('course', ['shortname' => $short]) ?: $generator->create_course([
        'shortname' => $short, 'fullname' => $name, 'visible' => 1,
        'summary' => 'Curso ficticio de pruebas del Sprint 2.',
    ]);
}
foreach ([['estudiante1', 'ALG101', 'student'], ['estudiante1', 'BIO102', 'student'],
        ['estudiante2', 'BIO102', 'student'], ['estudiante2', 'RES103', 'student'],
        ['docente1', 'BIO102', 'editingteacher']] as [$user, $course, $role]) {
    $generator->enrol_user($users[$user]->id, $courses[$course]->id, $role);
}
$managerrole = $DB->get_record('role', ['shortname' => 'manager'], '*', MUST_EXIST);
role_assign($managerrole->id, $users['autoridad1']->id, context_system::instance()->id);
$assigngenerator = $generator->get_plugin_generator('mod_assign');
foreach (['ALG101' => 'Ejercicios de ecuaciones', 'BIO102' => 'Informe de laboratorio',
        'RES103' => 'Proyecto reservado ORQUIDEA-73'] as $short => $name) {
    $course = $courses[$short];
    $assignment = $DB->get_record('assign', ['course' => $course->id, 'name' => $name]);
    if (!$assignment) {
        $assignment = $assigngenerator->create_instance([
            'course' => $course->id, 'name' => $name, 'duedate' => time() + 7 * DAYSECS,
            'assignsubmission_onlinetext_enabled' => 1,
        ]);
    }
    // Keep browser fixtures current when the seed is rerun; old deadlines make every
    // personalized weekly-plan example overdue and prevent testing future study blocks.
    $DB->set_field('assign', 'duedate', time() + 7 * DAYSECS, ['id' => $assignment->id]);
    if ($short === 'BIO102') {
        $cm = get_coursemodule_from_instance('assign', $assignment->id, $course->id);
        if (!$DB->record_exists('assign_submission', ['assignment' => $assignment->id,
                'userid' => $users['estudiante2']->id])) {
            $assigngenerator->create_submission([
                'userid' => $users['estudiante2']->id, 'cmid' => $cm->id,
                'status' => 'submitted', 'onlinetext' => 'Entrega ficticia de Luis.',
            ]);
            grade_update('mod/assign', $course->id, 'mod', 'assign', $assignment->id, 0,
                ['userid' => $users['estudiante2']->id, 'rawgrade' => 85]);
        }
        \core\session\manager::set_user($users['estudiante2']);
        $assign = new assign(context_module::instance($cm->id), $cm, $course);
        $assign->submit_for_grading(new stdClass(), []);
        \core\session\manager::set_user(get_admin());
    }
}
if (!$DB->record_exists('event', ['name' => 'Inicio del segundo ciclo (demo)'])) {
    calendar_event::create([
        'name' => 'Inicio del segundo ciclo (demo)', 'eventtype' => 'site',
        'courseid' => SITEID, 'userid' => get_admin()->id, 'groupid' => 0,
        'timestart' => time() + 30 * DAYSECS, 'timeduration' => 0, 'visible' => 1,
    ], false);
}
set_config('sessiontimeout', 1800);
set_config('guestloginbutton', 1);
set_config('enablemycourses', 1);
set_config('enablemyhome', 1);
set_config('curlsecurityallowedport', '8000');
set_config('curlsecurityblockedhosts', '');
set_config('sitepolicy', '');
echo json_encode(['users' => array_map(fn($user) => $user->id, $users),
    'courses' => array_map(fn($course) => $course->id, $courses)], JSON_PRETTY_PRINT) . PHP_EOL;
