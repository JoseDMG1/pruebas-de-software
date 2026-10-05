<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

define('CLI_SCRIPT', true);
require(dirname(__DIR__, 3) . '/config.php');

$courseids = $DB->get_fieldset_select(
    'course',
    'id',
    'id <> :siteid',
    ['siteid' => SITEID],
    'id ASC'
);
echo json_encode(
    ['course_ids' => array_map('intval', $courseids)],
    JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES
) . PHP_EOL;
