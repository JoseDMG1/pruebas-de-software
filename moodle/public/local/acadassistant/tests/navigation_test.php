<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

namespace local_acadassistant;

defined('MOODLE_INTERNAL') || die();

/** Tests the public global-navigation extension for personal Moodle accounts. */
final class navigation_test extends \advanced_testcase {
    public function test_authenticated_person_sees_assistant_in_site_primary_navigation(): void {
        global $PAGE;

        $this->resetAfterTest();
        $this->setAdminUser();
        $PAGE->set_url('/');
        $navigation = new \core\navigation\views\primary($PAGE);
        $navigation->initialise();

        $node = $navigation->find('local_acadassistant', \navigation_node::TYPE_CUSTOM);
        $this->assertNotNull($node);
        $this->assertSame('/local/acadassistant/index.php', $node->action->out_as_local_url());
    }

    public function test_authenticated_person_sees_global_assistant_navigation_link(): void {
        global $PAGE;

        $this->resetAfterTest();
        $this->setAdminUser();
        require_once(__DIR__ . '/../lib.php');
        $navigation = new \global_navigation($PAGE);

        $node = $navigation->find('local_acadassistant', \navigation_node::TYPE_CUSTOM);
        $this->assertNotNull($node);
        $this->assertSame('/local/acadassistant/index.php', $node->action->out_as_local_url());
    }

    public function test_guest_does_not_receive_assistant_in_site_primary_navigation(): void {
        global $PAGE;

        $this->resetAfterTest();
        $this->setGuestUser();
        $PAGE->set_url('/');
        $navigation = new \core\navigation\views\primary($PAGE);
        $navigation->initialise();

        $this->assertFalse($navigation->find('local_acadassistant', \navigation_node::TYPE_CUSTOM));
    }

    public function test_guest_does_not_receive_global_assistant_navigation_link(): void {
        global $PAGE;

        $this->resetAfterTest();
        $this->setGuestUser();
        require_once(__DIR__ . '/../lib.php');
        $navigation = new \global_navigation($PAGE);

        local_acadassistant_extend_navigation($navigation);

        $this->assertFalse($navigation->find('local_acadassistant', \navigation_node::TYPE_CUSTOM));
    }
}
