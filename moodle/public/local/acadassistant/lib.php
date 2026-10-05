<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

defined('MOODLE_INTERNAL') || die();

/** Add the assistant to global navigation for personal authenticated accounts. */
function local_acadassistant_extend_navigation(global_navigation $navigation): void {
    if (!isloggedin() || isguestuser()) {
        return;
    }

    $node = $navigation->add(
        get_string('assistant', 'local_acadassistant'),
        new moodle_url('/local/acadassistant/index.php'),
        navigation_node::TYPE_CUSTOM,
        null,
        'local_acadassistant'
    );
    $node->showinflatnavigation = true;
}
