<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

namespace local_acadassistant;

defined('MOODLE_INTERNAL') || die();

/** Connects the assistant to Moodle's site primary navigation. */
final class hook_callbacks {
    /** Add the assistant only for authenticated personal accounts. */
    public static function extend_primary_navigation(\core\hook\navigation\primary_extend $hook): void {
        if (!isloggedin() || isguestuser()) {
            return;
        }
        $hook->get_primaryview()->add(
            get_string('assistant', 'local_acadassistant'),
            new \moodle_url('/local/acadassistant/index.php'),
            \navigation_node::TYPE_CUSTOM,
            null,
            'local_acadassistant'
        );
    }
}
