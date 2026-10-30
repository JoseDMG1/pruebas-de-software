<?php
// Local academic records for the university learning environment.
define('CLI_SCRIPT', true);
require('/var/www/moodle/config.php');
require_once($CFG->libdir . '/testing/generator/lib.php');
require_once($CFG->libdir . '/gradelib.php');
require_once($CFG->dirroot . '/calendar/lib.php');
require_once($CFG->dirroot . '/mod/assign/locallib.php');
require_once($CFG->dirroot . '/mod/assign/lib.php');

if ($CFG->wwwroot !== 'http://127.0.0.1:8088' || !getenv('MOODLE_DEMO_PASSWORD')) {
    throw new RuntimeException('This fixture script is restricted to the local test site.');
}
$legacyadmin = $DB->get_record('user', ['username' => 'admin_sprint2']);
if ($legacyadmin) {
    $DB->set_field('user', 'username', 'admin_udv', ['id' => $legacyadmin->id]);
}
\core\session\manager::set_user(get_admin());
$DB->set_field('course', 'fullname', 'Universidad del Valle', ['id' => SITEID]);
$DB->set_field('course', 'shortname', 'UDV', ['id' => SITEID]);
$generator = new testing_data_generator();
$users = [];
foreach ([
    'estudiante1' => ['Ana', 'Torres'],
    'estudiante2' => ['Luis', 'Mendoza'],
    'docente1' => ['Carla', 'Rojas'],
    'docente2' => ['Diego', 'Salinas'],
    'docente3' => ['Valeria', 'Núñez'],
    'docente4' => ['Jorge', 'Rivas'],
    'autoridad1' => ['Mario', 'Salazar'],
] as $username => [$firstname, $lastname]) {
    $users[$username] = $DB->get_record('user', ['username' => $username]) ?: $generator->create_user([
        'username' => $username,
        'firstname' => $firstname,
        'lastname' => $lastname,
        'email' => $username . '@udv.edu.pe',
        'password' => getenv('MOODLE_DEMO_PASSWORD'),
        'lang' => 'en',
    ]);
    $DB->set_field('user', 'firstname', $firstname, ['id' => $users[$username]->id]);
    $DB->set_field('user', 'lastname', $lastname, ['id' => $users[$username]->id]);
    $DB->set_field('user', 'email', $username . '@udv.edu.pe', ['id' => $users[$username]->id]);
    $DB->set_field('user', 'timezone', 'America/Lima', ['id' => $users[$username]->id]);
    $users[$username]->firstname = $firstname;
    $users[$username]->lastname = $lastname;
}
$definitions = [
    'ALG101' => ['Algebra 101', 'Fundamentos de algebra, ecuaciones, funciones y modelado. Docente: Carla Rojas.'],
    'BIO102' => ['Biologia 102', 'Biologia celular, genetica y ecologia con practicas de laboratorio. Docente: Carla Rojas.'],
    'RES103' => ['Metodología de Investigación 103', 'Fundamentos de investigación académica, diseño metodológico y análisis de fuentes. Docente: Carla Rojas.'],
    'PROG104' => ['Programacion 104', 'Algoritmos, estructuras de datos, pruebas automatizadas y proyecto integrador. Docente: Carla Rojas.'],
    'COM105' => ['Comunicacion Academica 105', 'Lectura critica, escritura argumentativa y referencias academicas. Docente: Carla Rojas.'],
    'EST106' => ['Estadistica 106', 'Estadistica descriptiva, probabilidad, distribuciones y muestreo. Docente: Carla Rojas.'],
    'FIS107' => ['Fisica General 107', 'Cinematica, dinamica, energia y medicion experimental. Docente: Carla Rojas.'],
    'ING108' => ['Ingles Academico 108', 'Comprension de textos, escritura academica y presentaciones breves. Docente: Carla Rojas.'],
    'DIS109' => ['Diseno Digital 109', 'Prototipos, jerarquia visual, usabilidad y diseno accesible. Docente: Carla Rojas.'],
];
$instructors = ['ALG101' => 'docente1', 'BIO102' => 'docente1', 'RES103' => 'docente1',
    'PROG104' => 'docente2', 'EST106' => 'docente2', 'COM105' => 'docente3',
    'ING108' => 'docente3', 'FIS107' => 'docente4', 'DIS109' => 'docente4'];
$courses = [];
foreach ($definitions as $short => [$name, $summary]) {
    $summary = preg_replace('/ Docente:.*$/u', '', $summary) . ' Docente: ' .
        fullname($users[$instructors[$short]]) . '.';
    $courses[$short] = $DB->get_record('course', ['shortname' => $short]);
    if (!$courses[$short]) {
        $courses[$short] = $generator->create_course([
            'shortname' => $short, 'fullname' => $name, 'visible' => 1,
            'summary' => $summary,
            'startdate' => strtotime('2026-08-24 00:00:00 America/Lima'),
            'enddate' => strtotime('2026-12-23 23:59:59 America/Lima'),
        ]);
    } else {
        $DB->set_field('course', 'fullname', $name, ['id' => $courses[$short]->id]);
        $DB->set_field('course', 'summary', $summary,
            ['id' => $courses[$short]->id]);
        $courses[$short]->fullname = $name;
    }
}
$studentcourses = [
    'estudiante1' => ['ALG101', 'BIO102', 'PROG104', 'COM105', 'EST106', 'FIS107', 'ING108'],
    'estudiante2' => ['BIO102', 'RES103', 'PROG104', 'DIS109'],
];
foreach ($studentcourses as $username => $shortnames) {
    foreach ($shortnames as $short) {
        $generator->enrol_user($users[$username]->id, $courses[$short]->id, 'student');
    }
}
// Each course has an assigned instructor, with native enrolments and capabilities.
foreach ($instructors as $short => $teacher) {
    foreach (['docente1', 'docente2', 'docente3', 'docente4'] as $username) {
        if ($username === $teacher) {
            $generator->enrol_user($users[$username]->id, $courses[$short]->id, 'editingteacher');
        } else {
            foreach (enrol_get_instances($courses[$short]->id, true) as $instance) {
                if ($instance->enrol === 'manual') {
                    enrol_get_plugin('manual')->unenrol_user($instance, $users[$username]->id);
                }
            }
        }
    }
}
$managerrole = $DB->get_record('role', ['shortname' => 'manager'], '*', MUST_EXIST);
role_assign($managerrole->id, $users['autoridad1']->id, context_system::instance()->id);
foreach ($DB->get_records('assign', ['course' => $courses['RES103']->id]) as $legacyassignment) {
    if (str_starts_with($legacyassignment->name, 'Proyecto reservado ')) {
        $DB->set_field('assign', 'name', 'Proyecto de investigación exploratoria', ['id' => $legacyassignment->id]);
    }
}
$seedtime = time();
$assignments = [
    'ALG101' => [['Ejercicios de ecuaciones', 7, 'Resuelve sistemas de ecuaciones y adjunta el procedimiento.']],
    'BIO102' => [['Informe de laboratorio', 7, 'Entrega hipótesis, metodología, resultados y una conclusión sustentada.']],
    'RES103' => [
        ['Proyecto de investigación aplicada', 7, 'Presenta la pregunta de investigación, una revisión de fuentes y un plan de trabajo. Código de curso: INV-MET-2026.'],
        ['Proyecto de investigación exploratoria', 11, 'Presenta los antecedentes, las preguntas de estudio y las fuentes consultadas.'],
    ],
    'PROG104' => [
        ['Práctica de algoritmos', 4, 'Entrega código fuente, pruebas y una breve explicación de complejidad.'],
        ['Proyecto integrador de programación', 12, 'Sube un archivo comprimido con README, código y pruebas automatizadas.'],
    ],
    'COM105' => [['Reseña crítica de artículo', 3, 'Resume la tesis, presenta una evaluación argumentada y cita el artículo.']],
    'EST106' => [
        ['Análisis descriptivo de datos', 3, 'Incluye una tabla, un gráfico pertinente y una interpretación en palabras.'],
        ['Práctica de probabilidad', 10, 'Resuelve los problemas y muestra el procedimiento utilizado.'],
    ],
    'FIS107' => [['Informe de movimiento', 8, 'Declara unidades, procedimiento, incertidumbre y conclusión.']],
    'ING108' => [
        ['Presentación oral', 5, 'Prepara una presentación de cuatro a seis minutos con referencias.'],
        ['Bitácora de aprendizaje', 13, 'Registra vocabulario, práctica y una reflexión semanal.'],
    ],
    'DIS109' => [['Prototipo accesible', 9, 'Entrega el flujo principal y explica decisiones de accesibilidad.']],
];
$assigngenerator = $generator->get_plugin_generator('mod_assign');
foreach ($assignments as $short => $courseassignments) {
    $course = $courses[$short];
    foreach ($courseassignments as [$name, $days, $intro]) {
        $assignment = $DB->get_record('assign', ['course' => $course->id, 'name' => $name]);
        if (!$assignment) {
            $assignment = $assigngenerator->create_instance([
                'course' => $course->id, 'name' => $name, 'intro' => $intro,
                'introformat' => FORMAT_PLAIN, 'duedate' => $seedtime + $days * DAYSECS,
                'grade' => 100, 'assignsubmission_onlinetext_enabled' => 1,
            ]);
        }
        // Relative due dates keep the demo useful when it is prepared again later.
        $DB->set_field('assign', 'duedate', $seedtime + $days * DAYSECS, ['id' => $assignment->id]);
        $DB->set_field('assign', 'intro', $intro, ['id' => $assignment->id]);
        $assignment->duedate = $seedtime + $days * DAYSECS;
        $assignment->intro = $intro;
        assign_prepare_update_events($assignment);
    }
}
$ensure_submission = static function(string $short, string $name, string $username, float $grade)
        use ($DB, $users, $courses, $assigngenerator, $instructors): void {
    $course = $courses[$short];
    $assignment = $DB->get_record('assign', ['course' => $course->id, 'name' => $name], '*', MUST_EXIST);
    $cm = get_coursemodule_from_instance('assign', $assignment->id, $course->id);
    $created = false;
    $submission = $DB->get_record('assign_submission', ['assignment' => $assignment->id,
        'userid' => $users[$username]->id]);
    if (!$submission) {
        $assigngenerator->create_submission([
            'userid' => $users[$username]->id, 'cmid' => $cm->id,
            'status' => 'submitted', 'onlinetext' => 'Entrega académica de ' . $users[$username]->firstname . '.',
        ]);
        $created = true;
        $submission = $DB->get_record('assign_submission', ['assignment' => $assignment->id,
            'userid' => $users[$username]->id], '*', MUST_EXIST);
    }
    if ($created || $submission->status !== 'submitted') {
        \core\session\manager::set_user($users[$username]);
        $assign = new assign(context_module::instance($cm->id), $cm, $course);
        $assign->submit_for_grading(new stdClass(), []);
        \core\session\manager::set_user(get_admin());
    }
    $DB->set_field('assignsubmission_onlinetext', 'onlinetext',
        'Entrega académica: se adjuntan el desarrollo, los resultados y las conclusiones.',
        ['submission' => $submission->id]);
    // Save through the assignment API so its grading screen and the gradebook agree.
    \core\session\manager::set_user($users[$instructors[$short]]);
    $assign = new assign(context_module::instance($cm->id), $cm, $course);
    $assign->save_grade($users[$username]->id, (object)[
        'grade' => $grade, 'attemptnumber' => -1, 'sendstudentnotifications' => false,
        'assignfeedbackcomments_editor' => [
            'text' => 'Trabajo revisado: desarrollo y resultados registrados.', 'format' => FORMAT_PLAIN,
        ],
    ]);
    \core\session\manager::set_user(get_admin());
};
$ensure_submission('PROG104', 'Práctica de algoritmos', 'estudiante1', 92);
$ensure_submission('BIO102', 'Informe de laboratorio', 'estudiante2', 85);

// Keep Moodle's visible calendar aligned with the institutional calendar.
$DB->delete_records('event', ['name' => 'Inicio del segundo ciclo (demo)']);
if (!$DB->record_exists('event', ['name' => 'Semana de exámenes finales 2026-II'])) {
    calendar_event::create([
        'name' => 'Semana de exámenes finales 2026-II', 'eventtype' => 'site',
        'courseid' => SITEID, 'userid' => get_admin()->id, 'groupid' => 0,
        'timestart' => strtotime('2026-12-14 08:00:00 America/Lima'),
        'timeduration' => 5 * DAYSECS, 'visible' => 1,
    ], false);
}
$programmingevent = 'Asesoría del proyecto integrador';
if (!$DB->record_exists('event', ['name' => $programmingevent, 'courseid' => $courses['PROG104']->id])) {
    calendar_event::create([
        'name' => $programmingevent, 'eventtype' => 'course',
        'courseid' => $courses['PROG104']->id, 'userid' => get_admin()->id, 'groupid' => 0,
        'timestart' => time() + 6 * DAYSECS, 'timeduration' => HOURSECS,
        'visible' => 1, 'description' => 'Asesoría abierta para estudiantes del proyecto integrador.',
    ], false);
}
foreach ($courses as $course) {
    rebuild_course_cache($course->id, true);
}
set_config('timezone', 'America/Lima');
set_config('sessiontimeout', 1800);
set_config('guestloginbutton', 1);
set_config('enablemycourses', 1);
set_config('enablemyhome', 1);
set_config('curlsecurityallowedport', '8000');
set_config('curlsecurityblockedhosts', '');
set_config('sitepolicy', '');
echo json_encode(['users' => array_map(fn($user) => $user->id, $users),
    'courses' => array_map(fn($course) => $course->id, $courses)], JSON_PRETTY_PRINT) . PHP_EOL;
